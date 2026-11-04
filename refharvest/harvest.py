#!/usr/bin/env python3
"""python harvest.py --mode items --targets config/targets.json
   python harvest.py --mode structure --targets config/targets.json --out out"""
import argparse, json, os, sys, time
from urllib.parse import urlparse

import db, extract, fetch
from config.adapters import for_host


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--mode", choices=["items", "structure"], default="items")
    ap.add_argument("--db", default="data/harvest.db")
    ap.add_argument("--out", default="out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=3.5)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--include-done", action="store_true")
    ap.add_argument("--export", default=None)
    a = ap.parse_args()

    con = db.connect(a.db)
    targets = json.load(open(a.targets))
    if not a.include_done:
        targets = [t for t in targets if not t.get("skip")]
    if a.only:
        targets = [t for t in targets if t.get("status") == a.only]
    if a.limit:
        targets = targets[:a.limit]

    total_new = 0
    for i, t in enumerate(targets, 1):
        url = t["url"]
        adapter = for_host(urlparse(url).netloc)
        use_render = a.render or t.get("render") or adapter.get("render")
        try:
            html = fetch.get(url, render=bool(use_render))
        except fetch.Blocked as e:
            db.run_log(con, a.mode, url, False, f"blocked {e}")
            print(f"[{i}/{len(targets)}] BLOCKED {url}")
            time.sleep(a.delay)
            continue
        except Exception as e:                       # noqa: BLE001
            db.run_log(con, a.mode, url, False, str(e))
            print(f"[{i}/{len(targets)}] FAIL {url} {e}")
            time.sleep(a.delay)
            continue

        soup = extract.soup_of(html)
        if a.mode == "structure":
            rec = extract.structure(soup, url)
            os.makedirs(a.out, exist_ok=True)
            name = f"{t.get('dept','x')}_{abs(hash(url)) % 10**8}.json"
            json.dump(rec, open(os.path.join(a.out, name), "w"), indent=2)
            print(f"[{i}/{len(targets)}] cards={rec['card_repeats']} "
                  f"facets={len(rec['facets'])} {url}")
        else:
            recs = extract.items_from(soup, url, adapter,
                                      t.get("dept"), urlparse(url).netloc)
            for r in recs:
                db.upsert(con, r)
            total_new += len(recs)
            db.run_log(con, a.mode, url, True, f"{len(recs)} items")
            print(f"[{i}/{len(targets)}] +{len(recs)} items {url}")
        time.sleep(a.delay)

    if a.export:
        n = db.export(con, a.export)
        print(f"exported {n} ranked items -> {a.export}")
    print(f"done, {total_new} item records")


if __name__ == "__main__":
    main()