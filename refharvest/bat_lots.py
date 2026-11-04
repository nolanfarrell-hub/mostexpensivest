#!/usr/bin/env python3
"""Bring a Trailer live-lot puller for THE ROAD.
BaT embeds its current auctions as a JSON lot array inside the page (title,
current_bid, noreserve, year, sold_text, thumbnail_url, url). We parse that
embedded JSON into the harvest DB as dept='road' items with the bid recorded.

Free + live: BaT serves the data server-side; no auth, no paid API.
Sold/active state comes from the lot's own fields, and the current bid is the
market's live read on value. Repeat-sale rarity is derived at score time.
"""
import json, re, sys
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

# url -> dept. Add category pages here to widen the feed (free, same shape).
PAGES = {
    "https://bringatrailer.com/ferrari/": "road",
}

def extract_lots(html):
    lots = []
    for m in re.finditer(r'"current_bid_formatted":"([^"]*)"', html):
        anchor = m.start()
        depth = 0; start = anchor
        for k in range(anchor, max(0, anchor - 8000), -1):
            ch = html[k]
            if ch == '}':
                depth += 1
            elif ch == '{':
                if depth == 0:
                    start = k; break
                depth -= 1
        depth = 0; end = len(html)
        for k in range(start, len(html)):
            ch = html[k]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = k + 1; break
        try:
            lots.append(json.loads(html[start:end]))
        except Exception:
            continue
    return lots

def main():
    con = db.connect("data/harvest.db")
    total = 0
    for url, dept in PAGES.items():
        try:
            html = fetch.get(url)
        except Exception as e:
            print(f"[{url}] FAIL {e}")
            continue
        lots = extract_lots(html)
        if not lots:
            print(f"[{url}] 0 lots (page shape changed?)")
            continue
        n = 0
        for o in lots:
            title = re.sub(r"\s+", " ", o.get("title") or "").strip()
            if not title or not o.get("url"):
                continue
            bid = o.get("current_bid")
            rec = {
                "dept": dept, "source": "bringatrailer.com",
                "url": o["url"],
                "title": f"{o.get('year')} {title}".strip() if o.get("year") else title,
                "ask_cents": (int(bid) * 100) if bid else None,
                "currency": o.get("currency") or "USD",
                "condition": "No Reserve" if o.get("noreserve") else ("Sold" if o.get("sold_text") else "Live"),
                "spec": {
                    "year": o.get("year"), "noreserve": bool(o.get("noreserve")),
                    "sold": bool(o.get("sold_text")), "watchers": o.get("watchers"),
                    "views": o.get("views"), "active": bool(o.get("active")),
                    "excerpt": (o.get("excerpt") or "")[:240],
                    "category": list((o.get("categories") or []) or []),
                },
                "fallback_url": ("https://bringatrailer.com/ferrari/"),
            }
            db.upsert(con, rec)
            n += 1
        print(f"[{url}] +{n} lots (dept {dept})")
        total += n
    print(f"done, {total} BaT lots this run")

if __name__ == "__main__":
    main()
