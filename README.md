# vitasync-faq-crawler

Sammelt deutsch- und englischsprachige Gesundheits-FAQs (Antworten in Originalsprache, Feld `lang`) für die VitaSync-RAG-Datenbank.

**Starten:** Tab *Actions* → *FAQ crawlen* → *Run workflow*. Jede Quelle läuft als eigener paralleler Job (Matrix), ein Merge-Job dedupliziert quellenübergreifend. Ergebnis: `faqs.json` + `report.json` im Repo (und als Artifact).

Felder pro Eintrag: `id, question, answer, source, url, license, lang`.

- Respektiert robots.txt, 1,5 s Pause pro Host.
- Filter (PII, Dosierung/Diagnose, Länge, Sprache) in `crawl.py` – die R1–R6-Regeln sind dort nur angenähert und müssen angepasst werden.
- Quellen/Lizenzen in `sources.yaml`. Lizenz vor Produktivnutzung je Quelle klären.
- Die Anzahl ergibt sich aus den Quellen; 10 000 sind nicht garantiert.

## KI-Prüfung: sind das generelle Gesundheitsfragen?

`classify_ai.py` lässt Claude jeden Eintrag aus `faqs_clean.json` prüfen (Urteil: `general_health`, `not_health`, `context_dependent`, `personal_case`; dazu, ob die Antwort die Frage beantwortet).

**API-Key eintragen:** Repo → *Settings* → *Secrets and variables* → *Actions* → *New repository secret* → Name `ANTHROPIC_API_KEY`, Wert = dein Key. Den Key niemals in eine Datei im Repo schreiben.

**Starten:** *Actions* → *KI-Pruefung der FAQs* → *Run workflow*. Erst mit `limit` 100 testen, dann `0` für alle. Abgebrochene Läufe setzen automatisch fort (`ai_check/results.jsonl`).

Ergebnis: `faqs_ai_checked.json` (behalten), `faqs_ai_rejected.json` (mit Grund), `ai_report.json`.
