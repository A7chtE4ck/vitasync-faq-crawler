#!/usr/bin/env python3
"""Schreibt faqs_clean.json als TXT-Dateien mit je 20 Einträgen (Format: 'ID. Frage' + Antwort)."""
import json, os, sys
src = sys.argv[1] if len(sys.argv) > 1 else "faqs_clean.json"
out = sys.argv[2] if len(sys.argv) > 2 else "txt_chunks"
per = 20
os.makedirs(out, exist_ok=True)
d = json.load(open(src, encoding="utf-8"))
for i in range(0, len(d), per):
    part = d[i:i + per]
    name = f"{out}/faqs_{part[0]['id']:04d}-{part[-1]['id']:04d}.txt"
    open(name, "w", encoding="utf-8").write("\n\n".join(f"{e['id']}. {e['question']}\n{e['answer']}" for e in part) + "\n")
print(len(d), "Einträge ->", -(-len(d) // per), "Dateien")
