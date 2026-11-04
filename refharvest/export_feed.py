#!/usr/bin/env python3
"""Export the harvest DB to out/feed.json (ranked, by dept) + a flat list.
The site pages and any future consumer read one schema-agnostic file.

Each record carries the THREE separate 0-5 scores (never blended) plus the
live/fallback link and image path, so the shared market layer can render cards
and the browser-side filter rail without touching the DB.
"""
import json, sqlite3, os

def connect(path="data/harvest.db"):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con

def main():
    con = connect()
    rows = con.execute("SELECT * FROM items WHERE rank IS NOT NULL").fetchall()
    items = []
    for r in rows:
        spec = json.loads(r["spec_json"] or "{}")
        live = (r["state"] == "live" and not r["fallback_active"])
        items.append({
            "dept": r["dept"], "rank": r["rank"], "source": r["source"],
            "title": r["title"], "ask": (r["ask_cents"] or 0) / 100 or None,
            "currency": r["currency"], "condition": r["condition"],
            "scores": {"value": r["s_value"], "rarity": r["s_quality"],
                       "investment": r["s_desirability"]},
            "link": r["url"] if live else (r["fallback_url"] or r["url"]),
            "link_state": "live" if live else "fallback",
            "image": r["image_path"], "spec": spec,
        })
    os.makedirs("out", exist_ok=True)
    # dept-grouped (site manifest) + flat (generic consumer)
    by_dept = {}
    for it in items:
        by_dept.setdefault(it["dept"], []).append(it)
    payload = {"generated": __import__("datetime").datetime.now().isoformat(),
               "count": len(items), "departments": by_dept}
    with open("out/feed.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    print(f"wrote out/feed.json: {len(items)} ranked items across "
          f"{len(by_dept)} departments")

if __name__ == "__main__":
    main()
