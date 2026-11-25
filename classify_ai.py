#!/usr/bin/env python3
"""KI-Pruefung: Ist jeder Eintrag aus faqs_clean.json eine generelle Gesundheitsfrage?

API-Key: Umgebungsvariable ANTHROPIC_API_KEY
  - in GitHub Actions: Repo -> Settings -> Secrets and variables -> Actions -> New repository secret
    Name: ANTHROPIC_API_KEY
  - lokal: .env-Datei (siehe .env.example) oder `export ANTHROPIC_API_KEY=...`

Ergebnisse (werden laufend gespeichert, ein abgebrochener Lauf setzt automatisch fort):
  ai_check/results.jsonl      alle Einzelurteile
  faqs_ai_checked.json        nur Eintraege mit Urteil general_health und passender Antwort
  faqs_ai_rejected.json       alle uebrigen, mit Grund
  ai_report.json              Statistik
"""
import argparse, concurrent.futures as cf, json, os, re, sys, threading, time

SRC = "faqs_clean.json"
OUT_DIR = "ai_check"
CACHE = f"{OUT_DIR}/results.jsonl"
VERDICTS = {"general_health", "not_health", "context_dependent", "personal_case"}

SYSTEM = """Du pruefst Eintraege fuer eine FAQ-Datenbank eines Gesundheits-Chatbots (RAG).
Fuer jeden Eintrag (Frage + Antwortanfang) entscheidest du:

verdict:
- "general_health": Eine allgemeine Gesundheitsfrage, die unabhaengig von einer einzelnen Person oder Webseite verstaendlich ist
  (Krankheiten, Symptome, Vorsorge, Diagnose, Behandlung, Ernaehrung, Bewegung, Impfungen, Medikamente allgemein,
  psychische Gesundheit, Schwangerschaft, Kindergesundheit, Patientenrechte und digitale Gesundheitsangebote wie E-Rezept/ePA).
- "not_health": Anderes Thema (Verwaltung, Foerdergelder, Kurse/Camps, Webseiten-Bedienung, Datenschutzerklaerung, Spenden, Politik usw.).
- "context_dependent": Die Frage ist ohne den urspruenglichen Seitenkontext nicht verstaendlich ("Was sollte ich noch wissen?", "Wie lange dauert das?").
- "personal_case": Schildert einen individuellen Einzelfall und ist keine allgemeine Frage.

answer_ok (true/false): Beantwortet der Antwortanfang die Frage sinnvoll? false bei Teaser, Navigationstext, Werbung, Themenverfehlung
oder erkennbar falschem/gefaehrlichem Inhalt.

reason: hoechstens 12 Woerter, deutsch.

Antworte AUSSCHLIESSLICH mit einem JSON-Array, ein Objekt pro Eintrag, gleiche Reihenfolge:
[{"id": 1, "verdict": "general_health", "answer_ok": true, "reason": "..."}]
Kein weiterer Text, keine Markdown-Zaeune."""


def load_env():
    """Liest optional eine lokale .env (nie committen!)."""
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def snippet(text, n=60):
    w = text.split()
    return " ".join(w[:n]) + (" ..." if len(w) > n else "")


def make_prompt(batch):
    return "\n\n".join(f"[{e['id']}]\nFrage: {e['question']}\nAntwortanfang: {snippet(e['answer'])}" for e in batch)


def parse(text, ids):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError("kein JSON-Array in der Antwort")
    arr = json.loads(m.group(0))
    out = {}
    for o in arr:
        if int(o["id"]) in ids and o.get("verdict") in VERDICTS:
            out[int(o["id"])] = {"id": int(o["id"]), "verdict": o["verdict"], "answer_ok": bool(o.get("answer_ok", True)),
                                 "reason": str(o.get("reason", ""))[:200]}
    return out


class FakeClient:  # nur fuer --dry-run, kein API-Aufruf
    def classify(self, model, system, prompt):
        ids = [int(x) for x in re.findall(r"^\[(\d+)\]$", prompt, re.M)]
        return json.dumps([{"id": i, "verdict": "general_health", "answer_ok": True, "reason": "dry-run"} for i in ids])


class ApiClient:
    def __init__(self):
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("FEHLER: ANTHROPIC_API_KEY ist nicht gesetzt (GitHub Secret bzw. .env, siehe Kopf von classify_ai.py).")
        self.c = anthropic.Anthropic(max_retries=5)

    def classify(self, model, system, prompt):
        r = self.c.messages.create(model=model, max_tokens=4000, temperature=0, system=system,
                                   messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if getattr(b, "text", None))


def run_batch(client, model, batch):
    ids = {e["id"] for e in batch}
    got, last = {}, None
    for attempt in range(3):
        todo = [e for e in batch if e["id"] not in got]
        if not todo:
            break
        try:
            got.update(parse(client.classify(model, SYSTEM, make_prompt(todo)), {e["id"] for e in todo}))
        except Exception as ex:  # JSON-Fehler, Rate-Limit usw. -> erneut versuchen
            last = ex
            time.sleep(2 * (attempt + 1))
    for i in ids - set(got):
        got[i] = {"id": i, "verdict": "error", "answer_ok": False, "reason": f"Pruefung fehlgeschlagen: {last}"[:200]}
    return list(got.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("AI_MODEL", "claude-haiku-5-5"))
    ap.add_argument("--batch", type=int, default=25, help="Eintraege pro API-Aufruf")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="nur die ersten N unbearbeiteten Eintraege (0 = alle)")
    ap.add_argument("--dry-run", action="store_true", help="ohne API, alles als general_health")
    a = ap.parse_args()
    load_env()
    os.makedirs(OUT_DIR, exist_ok=True)
    data = json.load(open(SRC, encoding="utf-8"))
    done = {}
    if os.path.exists(CACHE):
        for line in open(CACHE, encoding="utf-8"):
            r = json.loads(line)
            if r["verdict"] != "error":
                done[r["id"]] = r
    todo = [e for e in data if e["id"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(data)} Eintraege, {len(done)} bereits geprueft, {len(todo)} jetzt zu pruefen (Modell {a.model})", flush=True)
    client = FakeClient() if a.dry_run else ApiClient()
    batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
    lock = threading.Lock()
    out = open(CACHE, "a", encoding="utf-8")
    n = 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for fut in cf.as_completed([ex.submit(run_batch, client, a.model, b) for b in batches]):
            res = fut.result()
            with lock:
                for r in res:
                    out.write(json.dumps(r, ensure_ascii=False) + "\n")
                    done[r["id"]] = r if r["verdict"] != "error" else done.get(r["id"], r)
                out.flush()
                n += len(res)
                print(f"  {n}/{len(todo)} geprueft", flush=True)
    out.close()
    # Auswertung ueber alle bisher vorliegenden Urteile
    kept, rej = [], []
    for e in data:
        r = done.get(e["id"])
        if not r:
            continue
        if r["verdict"] == "general_health" and r["answer_ok"]:
            kept.append(e)
        else:
            rej.append(dict(e, ai_verdict=r["verdict"], ai_answer_ok=r["answer_ok"], ai_reason=r["reason"]))
    json.dump(kept, open("faqs_ai_checked.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(rej, open("faqs_ai_rejected.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cnt = {}
    for r in rej:
        k = r["ai_verdict"] if r["ai_verdict"] != "general_health" else "answer_not_ok"
        cnt[k] = cnt.get(k, 0) + 1
    rep = {"total": len(data), "checked": len(done), "unchecked": len(data) - len(done), "kept": len(kept), "rejected": cnt}
    json.dump(rep, open("ai_report.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
