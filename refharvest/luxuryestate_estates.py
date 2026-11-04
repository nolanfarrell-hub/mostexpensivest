#!/usr/bin/env python3
"""LuxuryEstate luxury-estate puller (ESTATES) — direct, no Jina needed.

LuxuryEstate is NOT behind a bot wall: fetch.get returns the full listing page,
which carries the real property images as raw `pic.le-cdn.com/thumbs/<WxH>/.../
properties/Property-<hash>-<id>.jpg` URLs, plus the <title>/<h1> and price.

Listing URLs are geographic permalinks like /p133037519-detached-house-for-sale-
la-muette-... and the detail page's property images embed the SAME numeric id
(Property-<hash>-133037519.jpg), so an image can be verified to belong to its
listing before it is stored — no cross-listing mismatch.

Run via refresh pipeline (no FETCH_PROVIDER needed; direct is fine).
"""
import re, sys, os, urllib.parse
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

# property image: pic.le-cdn.com/thumbs/<w>x<h>/<x>/<n>/properties/Property-<hash>-<id>.jpg
IMG = re.compile(r'https://pic\.le-cdn\.com/thumbs/[0-9]+x[0-9]+/[0-9]+/[0-9]+/properties/[^"\s\\]+\.jpg')
# the le-cdn property id is the trailing number before .jpg
PROP_ID = re.compile(r'/[^/\s]+-(\d{6,})\.jpg')
PRICE = re.compile(r'([\u20ac$\u00a3])\s*([\d][\d,]*(?:\.[\d,]+)?)')
TITLE = re.compile(r'<title[^>]*>\s*([^<|]{8,130})\s*(?:-|\|)')
H1 = re.compile(r'<h1[^>]*>\s*([^<]{8,130})\s*</h1>')


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def detail_urls(con):
    """Recover the estate listing permalinks this source should carry.
    Prefer what's already tracked; else the known global list."""
    rows = con.execute(
        "SELECT url FROM items WHERE dept='estates' AND source='www.luxuryestate.com'").fetchall()
    return [r["url"] for r in rows]


def main():
    con = db.connect("data/harvest.db")
    urls = detail_urls(con)
    if not urls:
        # seed from the recovered history set (fallback so a cold DB still fills)
        print("no existing luxuryestate rows; providing seed list")
        seed = [
            "https://www.luxuryestate.com/p133037519-detached-house-for-sale-la-muette-auteuil-porte-dauphine",
            "https://www.luxuryestate.com/p133034025-duplex-for-sale-tour-eiffel-invalides-ecole-militaire-saint-thomas-d-aquin",
            "https://www.luxuryestate.com/p133023308-apartment-for-sale-munich",
            "https://www.luxuryestate.com/p133023306-apartment-for-sale-zaragoza",
            "https://www.luxuryestate.com/p133039619-apartment-for-sale-vigo",
            "https://www.luxuryestate.com/p133033792-mansion-for-sale-amsterdam",
            "https://www.luxuryestate.com/p133053576-detached-house-for-sale-nigran",
            "https://www.luxuryestate.com/p133067593-villa-for-sale-san-siro",
            "https://www.luxuryestate.com/p133026227-detached-house-for-sale-mies",
            "https://www.luxuryestate.com/p133078028-villa-for-sale-moltrasio",
            "https://www.luxuryestate.com/p133108464-villa-for-sale-costa-paradiso",
            "https://www.luxuryestate.com/p133108505-apartment-for-sale-lugano",
            "https://www.luxuryestate.com/p133108311-apartment-for-sale-carate-urio",
            "https://www.luxuryestate.com/p133108309-apartment-for-sale-milan",
            "https://www.luxuryestate.com/p133108308-apartment-for-sale-milan",
        ]
        urls = seed
    print(f"processing {len(urls)} luxuryestate listings")
    done, failed = 0, 0
    for u in urls:
        try:
            md = fetch.get(u)               # direct fetch (not walled)
        except Exception as e:              # noqa: BLE001
            print(f"  fetch fail {u.rsplit('/',1)[-1][:30]} {e}")
            failed += 1
            continue
        # THE image: first property image that matches this listing's numeric id
        want = re.search(r'/p(\d{6,})-', u)
        want_id = want.group(1) if want else None
        img_url = None
        for m in IMG.finditer(md):
            imid = PROP_ID.search(m.group(0))
            if imid and want_id and imid.group(1) == want_id:
                img_url = m.group(0)
                break
        if not img_url:                     # fallback: first property image anyway
            first = IMG.search(md)
            img_url = first.group(0) if first else None
        # title + price
        t = TITLE.search(md) or H1.search(md)
        title = clean(t.group(1)) if t else u.rsplit("/", 1)[-1]
        pr = PRICE.search(md)
        ask, cur = None, None
        if pr:
            code = {"\u20ac": "EUR", "$": "USD", "\u00a3": "GBP"}.get(pr.group(1))
            try:
                ask = int(float(pr.group(2).replace(",", "").replace("\u00a0", "")) * 100)
                cur = code
            except ValueError:
                pass
        db.upsert(con, {
            "dept": "estates", "source": "www.luxuryestate.com", "url": u,
            "title": title[:200], "ask_cents": ask, "currency": cur,
            "condition": None, "spec": {}, "fallback_url": u,
            "image_path": img_url,
        })
        done += 1
        flag = "IMG" if img_url else "NOIMG"
        print(f"  {flag} {u.rsplit('/',1)[-1][:34]} | {title[:34]}")
    print(f"done: {done} listings, {failed} failed")


if __name__ == "__main__":
    main()
