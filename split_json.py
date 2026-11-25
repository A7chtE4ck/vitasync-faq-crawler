#!/usr/bin/env python3
"""Teilt faqs_clean.json in gültige JSON-Arrays <= 1 MB (1.000.000 Bytes)."""
import json, os, sys
LIMIT = 1_000_000
src = sys.argv[1] if len(sys.argv) > 1 else "faqs_clean.json"
out = sys.argv[2] if len(sys.argv) > 2 else "chunks"
os.makedirs(out, exist_ok=True)
data = json.load(open(src, encoding="utf-8"))
parts, cur, size = [], [], 2
for e in data:
    s = json.dumps(e, ensure_ascii=False)
    b = len(s.encode("utf-8")) + 2
    if cur and size + b > LIMIT:
        parts.append(cur); cur, size = [], 2
    cur.append(s); size += b
if cur: parts.append(cur)
base = os.path.splitext(os.path.basename(src))[0]
for i, p in enumerate(parts, 1):
    fn = f"{out}/{base}_{i:02d}.json"
    open(fn, "w", encoding="utf-8").write("[\n" + ",\n".join(p) + "\n]\n")
print(len(data), "Einträge ->", len(parts), "Dateien")
