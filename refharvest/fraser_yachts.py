#!/usr/bin/env python3
"""Fraser Yachts live listings puller for THE SEA.
Fraser embeds per-yacht Product JSON-LD (name, builder, built year, length,
beam, draft, speed, price, image, url) in the buy-a-yacht page. We parse those
into the harvest DB as dept='sea' items with the ask price.

Free + live: standard schema.org JSON-LD, no auth, no paid API.
"""
import json, re, sys
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

PAGES = {"https://www.fraseryachts.com/en/buy-a-yacht/": "sea"}

def extract_yachts(html):
    blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
    out = []
    for b in blocks:
        try:
            o = json.loads(b)
        except Exception:
            continue
        def walk(x):
            if isinstance(x, dict):
                if x.get("name") and ("offers" in x or "price" in x) and x.get("@type") == "Product":
                    out.append(x)
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(o)
    # dedupe by url
    seen = {}
    for it in out:
        if it.get("url") and it["url"] not in seen:
            seen[it["url"]] = it
    return list(seen.values())

def spec_val(props, name):
    for p in props or []:
        if isinstance(p, dict) and (p.get("name") or "").lower() == name.lower():
            return p.get("value")
    return None

def main():
    con = db.connect("data/harvest.db")
    total = 0
    for url, dept in PAGES.items():
        try:
            html = fetch.get(url)
        except Exception as e:
            print(f"[{url}] FAIL {e}")
            continue
        yachts = extract_yachts(html)
        if not yachts:
            print(f"[{url}] 0 yachts (page shape changed?)")
            continue
        n = 0
        for o in yachts:
            name = re.sub(r"\s+", " ", o.get("name") or "").strip()
            if not name or not o.get("url"):
                continue
            offers = o.get("offers") or {}
            price = offers.get("price") or o.get("price")
            cur = offers.get("priceCurrency") or "USD"
            props = o.get("additionalProperty") or []
            length = spec_val(props, "length")
            built = o.get("productionDate")
            brand = (o.get("brand") or {}).get("name") if isinstance(o.get("brand"), dict) else o.get("brand")
            img = o.get("image")
            rec = {
                "dept": dept, "source": "fraseryachts.com",
                "url": o["url"],
                "title": f"{name}",
                "ask_cents": (int(float(price)) * 100) if price else None,
                "currency": cur,
                "condition": "In stock" if offers.get("availability") else None,
                "spec": {
                    "builder": brand, "built": built,
                    "length_m": length, "beam_m": spec_val(props, "beam"),
                    "draft_m": spec_val(props, "draft"),
                    "max_speed_knt": spec_val(props, "max speed"),
                    "cruise_speed_knt": spec_val(props, "cruising speed"),
                    "mpn": o.get("mpn"),
                },
                "fallback_url": "https://www.fraseryachts.com/en/buy-a-yacht/",
                "_image_hint": img,
            }
            db.upsert(con, rec)
            n += 1
        print(f"[{url}] +{n} yachts (dept {dept})")
        total += n
    print(f"done, {total} Fraser yachts this run")

if __name__ == "__main__":
    main()
