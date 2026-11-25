# vitasync-faq-crawler

Sammelt deutschsprachige Gesundheits-FAQs für die VitaSync-RAG-Datenbank.

**Starten:** Tab *Actions* → *FAQ crawlen* → *Run workflow*. Ergebnis: `faqs.json` + `report.json` im Repo (und als Artifact).

Felder pro Eintrag: `id, question, answer, source, url, license, lang`.

- Respektiert robots.txt, 1,5 s Pause pro Host.
- Filter (PII, Dosierung/Diagnose, Länge, Sprache) in `crawl.py` – die R1–R6-Regeln sind dort nur angenähert und müssen angepasst werden.
- Quellen/Lizenzen in `sources.yaml`. Lizenz vor Produktivnutzung je Quelle klären.
- Die Anzahl ergibt sich aus den Quellen; 10 000 sind nicht garantiert.
