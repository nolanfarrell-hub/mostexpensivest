#!/usr/bin/env python3
"""Link health monitor. Dead -> promote fallback, record last-seen price."""
import argparse, time
import db, fetch

SOLD = ("sold", "no longer available", "withdrawn", "sale pending",
        "under offer", "reserved")


def classify(status, body):
    if status in (404, 410):
        return "dead"
    if status in (403, 429, 503) or status == 0:
        return "blocked"
    low = body.lower()
    if any(s in low for s in SOLD):
        return "sold"
    return "live"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/harvest.db")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=2.0)
    a = ap.parse_args()

    con = db.connect(a.db)
    q = "SELECT * FROM items WHERE state = 'live' ORDER BY last_checked"
    rows = con.execute(q + (" LIMIT ?" if a.limit else ""),
                       ((a.limit,) if a.limit else ())).fetchall()

    for r in rows:
        status = fetch.head_ok(r["url"])
        body = ""
        if status == 200:
            try:
                body = fetch.get(r["url"], tries=1)[:20000]
            except Exception:                        # noqa: BLE001
                pass
        verdict = classify(status, body)
        state = "live" if verdict == "blocked" else verdict
        fallback = 1 if verdict in ("dead", "sold") else 0
        con.execute("UPDATE items SET state=?, fallback_active=?, "
                    "last_checked=datetime('now') WHERE id=?",
                    (state, fallback, r["id"]))
        db.event(con, r["id"], verdict, f"http {status}")
        con.commit()
        print(f"{verdict:8} {r['url']}")
        time.sleep(a.delay)


if __name__ == "__main__":
    main()