#!/usr/bin/env python3
"""FAQ-Crawler fuer VitaSync. Respektiert robots.txt, extrahiert Q&A, filtert, dedupliziert."""
import html, json, re, time, unicodedata, collections
from urllib import robotparser
from urllib.parse import urljoin, urlparse, urldefrag
import requests, yaml
from bs4 import BeautifulSoup
from datasketch import MinHash, MinHashLSH

CFG = yaml.safe_load(open("sources.yaml", encoding="utf-8"))
ST = CFG["settings"]
SESSION = requests.Session()
SESSION.headers["User-Agent"] = ST["user_agent"]
STATS = collections.Counter()
_last = {}
_robots = {}

# ---------- Filter (an R1-R6 anpassen!) ----------
RE_PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|(?:\+|00)\d[\d /().-]{7,}\d|\b0\d{2,5}[ /-]?\d{4,}\b|\b[A-Z]{2}\d{2}(?: ?\d{4}){3,}")
RE_DOSE = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:mg|µg|mcg|ml|ie|i\.e\.|mmol)\b|\bdosierung\b|\btabletten?\b|\bpro tag einnehmen\b", re.I)
RE_DIAG = re.compile(r"\b(?:sie haben|sie leiden an|bei ihnen liegt)\b", re.I)
DE_WORDS = {"der","die","das","und","ist","nicht","mit","von","zu","den","ein","eine","auf","für","sich","auch","wird","können"}


def is_german(t):
    w = re.findall(r"[a-zäöüß]+", t.lower())
    return len(w) > 0 and sum(x in DE_WORDS for x in w) / len(w) > 0.12


def clean(raw):
    if "<" in raw:
        s = BeautifulSoup(raw, "lxml")
        for t in s(["script", "style", "nav", "form"]):
            t.decompose()
        raw = s.get_text(" ")
    t = unicodedata.normalize("NFC", html.unescape(raw))
    return re.sub(r"\s+", " ", t).strip()


def truncate(text, n=300):
    w = text.split()
    if len(w) <= n:
        return text
    cut = " ".join(w[:n])
    i = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:i + 1] if i > len(cut) * 0.4 else cut


# ---------- HTTP ----------
def allowed(url):
    host = urlparse(url).netloc
    if host not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = SESSION.get(f"https://{host}/robots.txt", timeout=20)
            rp.parse(r.text.splitlines() if r.ok else [])
        except Exception:
            rp.parse([])
        _robots[host] = rp
    return _robots[host].can_fetch(ST["user_agent"], url)


def get(url):
    if not allowed(url):
        STATS["robots_blocked"] += 1
        return None
    host = urlparse(url).netloc
    d = max(ST["delay_seconds"], _robots[host].crawl_delay(ST["user_agent"]) or 0)
    wait = _last.get(host, 0) + d - time.time()
    if wait > 0:
        time.sleep(wait)
    try:
        r = SESSION.get(url, timeout=30)
    except Exception:
        STATS["fetch_errors"] += 1
        return None
    finally:
        _last[host] = time.time()
    ct = r.headers.get("content-type", "")
    if r.status_code != 200 or not ("html" in ct or "xml" in ct):
        STATS["fetch_errors"] += 1
        return None
    return r.text


def sitemap_urls(src):
    host = urlparse(src["base"]).netloc
    seeds = []
    if allowed(src["base"] + "/") and host in _robots:
        seeds = list(_robots[host].site_maps() or [])
    seeds = seeds or [src["base"] + "/sitemap.xml"]
    out, seen = [], set()
    while seeds and len(out) < src["max_pages"] * 5:
        sm = seeds.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        x = get(sm)
        if not x:
            continue
        soup = BeautifulSoup(x, "xml")
        seeds += [l.text.strip() for l in soup.select("sitemap > loc")]
        out += [l.text.strip() for l in soup.select("url > loc")]
    return out


def in_scope(url, src):
    p = urlparse(url)
    return p.netloc == urlparse(src["base"]).netloc and any(p.path.startswith(x) for x in src["prefixes"])


# ---------- Extraktion ----------
def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def extract(soup):
    pairs = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except Exception:
            continue
        for o in _walk(data):
            if o.get("@type") == "Question" and isinstance(o.get("acceptedAnswer"), dict):
                pairs.append((o.get("name", ""), o["acceptedAnswer"].get("text", "")))
    for d in soup.find_all("details"):
        sm = d.find("summary")
        if sm:
            q = sm.get_text(" ")
            sm.extract()
            pairs.append((q, d.get_text(" ")))
    for h in soup.find_all(["h2", "h3", "h4"]):
        q = h.get_text(" ").strip()
        if not q.endswith("?"):
            continue
        lvl, parts = int(h.name[1]), []
        for sib in h.find_next_siblings():
            if sib.name and re.fullmatch(r"h[1-6]", sib.name) and int(sib.name[1]) <= lvl:
                break
            if sib.name in ("p", "ul", "ol", "div"):
                parts.append(sib.get_text(" "))
        pairs.append((q, " ".join(parts)))
    return pairs


def accept(q, a):
    if len(q.split()) < 5 or len(a.split()) < 15:
        STATS["too_short"] += 1
        return False
    if not q.rstrip().endswith("?"):
        STATS["not_question"] += 1
        return False
    if RE_PII.search(q + " " + a):
        STATS["dropped_pii"] += 1
        return False
    if RE_DOSE.search(a) or RE_DIAG.search(a):
        STATS["dropped_r1_r6"] += 1
        return False
    if "de" in ST["languages"] and not is_german(a):
        STATS["dropped_language"] += 1
        return False
    return True


# ---------- Dedup ----------
LSH = MinHashLSH(threshold=0.85, num_perm=128)
KEPT = []


def mh(q):
    w = re.findall(r"\w+", q.lower())
    m = MinHash(num_perm=128)
    for sh in set(w) | {a + " " + b for a, b in zip(w, w[1:])}:
        m.update(sh.encode())
    return m


def add(q, a, src, url):
    m = mh(q)
    hit = LSH.query(m)
    if hit:
        e = KEPT[int(hit[0])]
        STATS["duplicates"] += 1
        if len(a) > len(e["answer"]):
            e.update(answer=a, url=url)
        return
    LSH.insert(str(len(KEPT)), m)
    KEPT.append({"question": q, "answer": a, "source": src["name"], "url": url, "license": src["license"], "lang": "de"})


def main():
    total = 0
    try:
        for src in CFG["sources"]:
            urls = [u for u in sitemap_urls(src) if in_scope(u, src)]
            if not urls:
                urls = [src["base"] + src["prefixes"][0]]
            todo, seen, n = collections.deque(urls), set(urls), 0
            print(f"== {src['name']}: {len(urls)} Start-URLs", flush=True)
            while todo and n < src["max_pages"] and total < ST["max_total_pages"] and len(KEPT) < ST["target_count"]:
                url = todo.popleft()
                body = get(url)
                if not body:
                    continue
                n += 1
                total += 1
                STATS["pages"] += 1
                soup = BeautifulSoup(body, "lxml")
                for q, a in extract(soup):
                    q, a = clean(q), truncate(clean(a))
                    STATS["raw_pairs"] += 1
                    if accept(q, a):
                        add(q, a, src, url)
                if len(seen) < src["max_pages"] * 5:  # Link-Fallback, bleibt im Scope
                    for l in soup.find_all("a", href=True):
                        u = urldefrag(urljoin(url, l["href"]))[0]
                        if u not in seen and in_scope(u, src):
                            seen.add(u)
                            todo.append(u)
                if n % 100 == 0:
                    print(f"  {n} Seiten, {len(KEPT)} FAQ", flush=True)
    finally:
        out = [{"id": i + 1, **e} for i, e in enumerate(KEPT)]
        json.dump(out, open("faqs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        STATS["final"] = len(out)
        json.dump(dict(STATS), open("report.json", "w"), indent=2)
        print(json.dumps(dict(STATS), indent=2))


if __name__ == "__main__":
    main()
