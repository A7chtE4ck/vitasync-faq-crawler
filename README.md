# vitasync-faq-crawler

Sammelt deutsch- und englischsprachige Gesundheits-FAQs (Antworten in Originalsprache, Feld `lang`) für die VitaSync-RAG-Datenbank.

**Starten:** Tab *Actions* → *FAQ crawlen* → *Run workflow*. Jede Quelle läuft als eigener paralleler Job (Matrix), ein Merge-Job dedupliziert quellenübergreifend. Ergebnis: `faqs.json` + `report.json` im Repo (und als Artifact).

Felder pro Eintrag: `id, question, answer, source, url, license, lang`.

- Respektiert robots.txt, 1,5 s Pause pro Host.
- Filter (PII, Dosierung/Diagnose, Länge, Sprache) in `crawl.py` – die R1–R6-Regeln sind dort nur angenähert und müssen angepasst werden.
- Quellen/Lizenzen in `sources.yaml`. Lizenz vor Produktivnutzung je Quelle klären.
- Die Anzahl ergibt sich aus den Quellen; 10 000 sind nicht garantiert.
