#!/usr/bin/env python3
"""Export the harvest DB to out/feed.json (ranked, by dept) + a flat list.
The site pages and any future consumer read one schema-agnostic file.

Each record carries the THREE separate 0-5 scores (never blended) plus the
live/fallback link and image path, so the shared market layer can render cards
and the browser-side filter rail without touching the DB.
"""
import json, re, sqlite3, os

def connect(path="data/harvest.db"):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con

def _clean_title(r):
    """Normalize per-source titles so cards read cleanly, not as scraped text.
    Returns None when the row is junk (dealer blocks, nav noise) so the exporter
    can drop it rather than ship a broken card."""
    t = r["title"] or ""
    src = r["source"] or ""
    # junk: markdown image/dealer blocks accidentally captured as items
    if t.strip().startswith("![") or "dealer_listings" in t:
        return None
    if len(t.strip()) < 3:
        return None
    if src == "www.luxuryestate.com":
        # '4 bedroom luxury Flat for sale in Zaragoza, Spain - 133023306'
        # -> 'Flat in Zaragoza, Spain ' (drop room count, 'luxury', 'for sale', id)
        m = re.search(
            r"(?i)^(?:[0-9]+ (?:bedroom|room) )?"
            r"luxury?\s+(?:[0-9]+ (?:bedroom|room) )?"
            r"(Flat|Apartment|Villa|Detached House|Mansion|Duplex|House|Penthouse|"
            r"Townhouse|Chalet|Castle|Chateau|Maisonette|Studio|Loft)"
            r"\s+(?:for sale(?:d)? in|in)\s+(.+?)(?: - \d+)?$",
            t)
        if m:
            ptype = m.group(1); place = (m.group(2) or "").strip()
            if len(place) >= 4:
                return f"{ptype} in {place}"
    return t

def main():
    con = connect()
    rows = con.execute("SELECT * FROM items WHERE rank IS NOT NULL").fetchall()
    items = []
    dropped_junk = 0
    for r in rows:
        spec = json.loads(r["spec_json"] or "{}")
        live = (r["state"] == "live" and not r["fallback_active"])
        title = _clean_title(r)
        if title is None:
            dropped_junk += 1
            continue   # mis-extracted dealer/nav block — do not ship a broken card
        if len(title) > 80:
            title = title[:77].rstrip() + "\u2026"
        items.append({
            "dept": r["dept"], "rank": r["rank"], "source": r["source"],
            "title": title,
            "ask": (r["ask_cents"] or 0) / 100 or None,
            "currency": r["currency"], "condition": r["condition"],
            "scores": {"value": r["s_value"], "rarity": r["s_quality"],
                       "investment": r["s_desirability"]},
            "link": r["url"] if live else (r["fallback_url"] or r["url"]),
            "link_state": "live" if live else "fallback",
            "image": r["image_path"], "spec": spec,
        })
    print(f"export: {len(items)} kept, {dropped_junk} junk dropped")
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
