#!/usr/bin/env python3
"""Fuehrt parts/part_*.json zusammen: globale Deduplizierung, IDs, faqs.json + report.json."""
import glob, json, collections
from datasketch import MinHashLSH
import crawl

lsh = MinHashLSH(threshold=0.85, num_perm=128)
kept, stats = [], collections.Counter()
for f in sorted(glob.glob("parts/stats_*.json")):
    stats.update(json.load(open(f)))
stats["final_before_merge"] = 0
for f in sorted(glob.glob("parts/part_*.json")):
    for e in json.load(open(f, encoding="utf-8")):
        stats["final_before_merge"] += 1
        m = crawl.mh(e["question"])
        hit = lsh.query(m)
        if hit:
            stats["duplicates_cross_source"] += 1
            k = kept[int(hit[0])]
            if len(e["answer"]) > len(k["answer"]):
                k.update(answer=e["answer"], url=e["url"], source=e["source"], license=e["license"], lang=e["lang"])
            continue
        lsh.insert(str(len(kept)), m)
        kept.append(e)
out = [{"id": i + 1, **e} for i, e in enumerate(kept)]
json.dump(out, open("faqs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
stats["final"] = len(out)
stats["by_source"] = dict(collections.Counter(e["source"] for e in out))
stats["by_lang"] = dict(collections.Counter(e["lang"] for e in out))
json.dump(stats, open("report.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(json.dumps(stats, indent=2, ensure_ascii=False))
