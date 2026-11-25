#!/usr/bin/env python3
"""Zweite Qualitaetsstufe: bereinigt und filtert faqs.json -> faqs_clean.json (+ faqs_rejected.json, faqs_review.json)."""
import json, re, collections

SW = set("a an the of to in on for with and or is are be am was were do does did can could will would should i you we my me your our this that these those it its what how why when where which who whom there any some if as at by from not no about than then so just have has had get take taking long much many more most also other another".split()) | set("der die das den dem des ein eine einen einem einer und oder ist sind wird werden wie was wer wo wann warum welche welcher welches kann können muss man mich mir mein meine meiner ich sie wir es zu zum zur im in an auf für mit von bei nach gibt ob auch noch nur sich".split())
DEFINITIONAL = re.compile(r"^(was (ist|sind|bedeutet)|what (is|are|does)|wie (wird|werden|lässt|kann|können|häufig|verläuft|behandelt|erkennt)|welche (symptome|ursachen|risikofaktoren|behandlung)|how (is|are|can|does|do)|who is at)\b", re.I)
DEICTIC = re.compile(r"\b(it|this|that|these|those|they|dies\w*|dazu|damit|darüber|dafür|hierzu|dabei|konkret)\b", re.I)
FIRST = re.compile(r"\b(I|my|me|I'm|you|your|ich|mein\w*|mir)\b", re.I)
VAGUE_DE = re.compile(r"^(was ist mit|wie sieht das angebot|woran kann man sich|und wie|wie funktioniert das\?)", re.I)
OFFTOPIC_Q = re.compile(r"ukrain|flüchtling|refugee|\bvisa\b|survey|slider|accordion|spenden(nachweis|bescheinigung|quittung|aktion)|nutzungsbedingung|\bgrants?\b|audit|funding|small business|\bcamp\b|summer course|cooperative agreement|\bIRB\b|nutritionday|medical devices technical", re.I)
ADMIN_URL = re.compile(r"/(museum|wcms|grants|contracts|ccindex|spenderservice|spenden|drugservice|als/(join|abouttheregistry)|data-presentation|already-have-grant)\b|slider|faq-module", re.I)
NAV_Q = re.compile(r"wo finde ich|wohin wende|wohin gehen|ansprechpartner|weitere informationen|wo gibt es|where can i find|how can i learn more|how do i contact|what if i need more help|woran kann man sich orientieren|wer hilft", re.I)
VIDEO_A = re.compile(r"^(im folgenden video|erfahren sie in diesem video|das folgende video|in diesem video|watch |in this video|dieses video)", re.I)
LINKY_A = re.compile(r"^(artikel |ausführliche informationen|weitere informationen|mehr informationen|das portal |auf der website)", re.I)
BOILER = re.compile(r"cookie[- ]?(policy|banner|einstellungen|settings)|accept cookies|javascript|©|klicken sie hier|zum weiterlesen", re.I)
HYPE = re.compile(r"heilung garantiert|garantiert geheilt|guaranteed cure|100 ?% ?(sicher|wirksam) gegen", re.I)
DATED = re.compile(r"\b(20(19|20|21|22))\b")
URL = re.compile(r"https?://|www\.")

def cw(t):
    return [w for w in re.findall(r"[a-zäöüß]{3,}", t.lower()) if w not in SW]

def lang_of(t):
    w = re.findall(r"[a-zäöüß]+", t.lower())
    if not w: return None
    de = sum(x in {"der","die","das","und","ist","nicht","mit","von","zu","den","ein","eine","auf","für","sich","auch","wird","können"} for x in w)/len(w)
    en = sum(x in {"the","and","is","are","of","to","that","for","with","can","may","your","or","it","be","not","this"} for x in w)/len(w)
    return "de" if de > en and de > 0.08 else "en" if en > de and en > 0.08 else None

def norm_q(q):
    q = re.sub(r"^\s*(?:\d+(?:\.\d+)*\.?\s+)", "", q)                       # "01 ", "2.2 "
    q = re.sub(r"^(Gut zu wissen|Wichtiges in Kürze|Wichtig|Tipp|Hinweis|Achtung|Video)\s*[:\-–]?\s+", "", q)
    q = re.sub(r"\s+([,.;:?!])", r"\1", q)
    return re.sub(r"\s+", " ", q).strip()

def norm_a(a):
    a = re.split(r"\bZum Weiterlesen\b", a)[0]
    a = re.sub(r"\[?Symbolbild\]?\.?", "", a)
    a = re.sub(r"\bBild: ©[^.]*\.?", "", a)
    a = re.sub(r"\bBild: Krebsinformationsdienst, DKFZ\.?", "", a)
    a = re.sub(r"\b(Read more|For more information, click here|To find out more, click here|Click here)\b[^.]*\.?", "", a, flags=re.I)
    a = re.sub(r"\bclick here\b[^.]*\.?", "", a, flags=re.I)
    a = re.sub(r"^(Gut zu wissen|Wichtig|Tipp|Hinweis)\s*[:\-–]?\s+", "", a)
    a = re.sub(r"\s*\bWeiterlesen\b\s*", " ", a)
    a = re.sub(r"\s+([,.;:?!])", r"\1", a)
    return re.sub(r"\s+", " ", a).strip()

def slug_tokens(url):
    parts = re.split(r"[/\-_.]", url.split("//", 1)[-1].split("/", 1)[-1])
    return [p[:6].lower() for p in parts if len(p) >= 5 and p.lower() not in {"index","conditions","medicines","pregnancy","live-well","faqs","health","topics","themen","krankheiten","html","phtml"}]

def check(e):
    q, a, url = e["question"], e["answer"], e["url"]
    if (ADMIN_URL.search(url) and "/newsletter/" not in url) or OFFTOPIC_Q.search(q): return "off_topic"
    if VIDEO_A.search(a): return "video_teaser"
    if LINKY_A.search(a) or NAV_Q.search(q) or len(URL.findall(a)) >= 3: return "navigation_or_link_teaser"
    if BOILER.search(a): return "boilerplate"
    if HYPE.search(a): return "dubious_claim"
    if len(q.split()) < 4 or len(a.split()) < 15: return "too_short"
    if len(q.split()) >= 6 and lang_of(q) and lang_of(a) and lang_of(q) != lang_of(a): return "language_mismatch"
    qc = cw(q); sep = bool(re.search(r"[:–]", q))
    if VAGUE_DE.search(q) and not sep: return "context_dependent"
    if not sep and len(qc) <= 3 and DEICTIC.search(q) and not DEFINITIONAL.search(q): return "context_dependent"
    if len(qc) <= 1 and not DEFINITIONAL.search(q): return "context_dependent"
    if FIRST.search(q) and len(qc) <= 1 and not sep and not DEFINITIONAL.search(q): return "context_dependent"
    return None

def main():
    d = json.load(open("faqs.json", encoding="utf-8"))
    clean, rej, review, seen = [], [], [], set()
    for e in d:
        e = dict(e, question=norm_q(e["question"]), answer=norm_a(e["answer"]))
        r = check(e)
        key = re.sub(r"\W+", " ", e["question"].lower())
        if not r and key in seen: r = "duplicate_after_cleanup"
        if r:
            rej.append(dict(e, reason=r)); continue
        seen.add(key)
        ac = " ".join(cw(e["answer"])); qc = cw(e["question"])
        if qc and not any(w[:5] in ac for w in qc): review.append(dict(e, review="no_overlap"))
        elif DATED.search(e["answer"]): review.append(dict(e, review="dated_reference"))
        clean.append(e)
    clean = [{"id": i + 1, **{k: v for k, v in e.items() if k != "id"}} for i, e in enumerate(clean)]
    json.dump(clean, open("faqs_clean.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(rej, open("faqs_rejected.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(review, open("faqs_review.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep = {"input": len(d), "clean": len(clean), "rejected": dict(collections.Counter(x["reason"] for x in rej)),
           "review_flagged_but_kept": dict(collections.Counter(x["review"] for x in review)),
           "clean_by_source": dict(collections.Counter(e["source"] for e in clean)),
           "clean_by_lang": dict(collections.Counter(e["lang"] for e in clean))}
    json.dump(rep, open("report_clean.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
