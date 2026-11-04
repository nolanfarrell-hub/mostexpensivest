#!/usr/bin/env python3
"""JamesEdition France (Provence + Côte d'Azur) estate puller (ESTATES section).

The main estate feed pulls JamesEdition's global /real_estate/all, which rotates
and rarely includes France. The Provence and Côte-d'Azur region pages always
expose their featured listings with real thumbnails + clean link-titles, so this
puller guarantees France options stay on the estate page. Same SPA-behind-a-bot-
wall anatomy as jamesedition_estates.py — MUST run with FETCH_PROVIDER=jina.

Each region page renders one featured card:
  [<text> ![Image N: <desc, place>](img.jamesedition.com/listing_images/...)
   ...](real_estate/<slug>/<id> "<CLEAN TITLE>")   + price on the detail page

Parse the listing URL (2-segment), the inline image, the link-title attribute,
then fetch the detail page for the current price (like the main estate puller).
Upserts are idempotent on url; source is tagged 'jamesedition.fr' so the France
section is separate from the global feed and never overwrites it.
"""
import re, sys, os, time, json
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

REGIONS = {
    "provence": "https://www.jamesedition.com/real_estate/provence-france",
    "cote":     "https://www.jamesedition.com/real_estate/cote-dazur-france",
}
# 2-segment listing link: .../real_estate/<slug>/<id> "Clean Title"
# (region cards hold nested image-brackets, so match the URL token + optional title)
LINK = re.compile(r"\((https://www\.jamesedition\.com/real_estate/[^)/\s]+/[^)\s]+)"
                  r"(?:\s+\"([^\"]*)\")?\)", re.S)
# inline listing image URL (skip dealer/agent logos)
IMG = re.compile(r"!\[[^\]]*\]\((https://img\.jamesedition\.com/listing_images/[^)\s]+)")
# image alt carries place text; we prefer the link-title but keep alt as backup
TITLE_ALT = re.compile(r"!\[Image \d+: ([^\]]{6,160})\]\s*\(https://img\.jamesedition\.com/listing_images/")
PRICE = re.compile(r"([$€£])\s*([\d][\d,]*(?:\.[\d,]+)?)")
HERO = re.compile(r"https://img\.jamesedition\.com/listing_images/[^)\s\"']+")


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main():
    con = db.connect("data/harvest.db")
    if os.environ.get("FETCH_PROVIDER", "direct") != "jina":
        print("note: set FETCH_PROVIDER=jina for this puller")
    total = 0
    for region, url in REGIONS.items():
        try:
            md = fetch.get(url, recover=True)
        except Exception as e:            # noqa: BLE001
            print(f"[{region}] FAIL {e}")
            continue
        # each listing link; image + title nearby in the card text
        for m in LINK.finditer(md):
            u = m.group(1)
            if "page=" in u or u.endswith("#"):
                continue
            # card block: window back to the nearest inline image
            tail = md[max(0, m.start()-1200): m.start()]
            im = IMG.search(tail)
            img_url = im.group(1) if im else None
            ta = TITLE_ALT.search(tail)
            link_title = clean(m.group(2)) if m.group(2) else ""
            title = link_title or (clean(ta.group(1)) if ta else "") or u.rsplit("/",1)[-1]
            # preserve a stored image across re-runs (db.upsert overwrites image_path)
            cur = con.execute("SELECT image_path, ask_cents FROM items WHERE url=?", (u,)).fetchone()
            have_img = img_url or (cur and cur["image_path"])
            ask, cur2 = None, None
            # price from detail page (region card itself often has no figure)
            try:
                dmd = fetch.get(u)
                # price sits in the 'converted from €X' conversion line (~idx ~2800)
                pm = PRICE.search(dmd[:5000])
                if pm:
                    code = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}.get(pm.group(1))
                    try:
                        ask = int(float(pm.group(2).replace(",", "").replace("\u00a0","")) * 100)
                        cur2 = code
                    except ValueError:
                        pass
                if not img_url:
                    hero = HERO.search(dmd)
                    if hero:
                        have_img = hero.group(0)
                time.sleep(0.8)
            except Exception as e:        # noqa: BLE001
                print(f"  detail fail {u.rsplit('/',1)[-1][:30]} {e}")
            db.upsert(con, {
                "dept": "estates", "source": "jamesedition.fr",
                "url": u, "title": title[:200],
                "ask_cents": ask, "currency": cur2, "condition": None,
                "spec": {"region": region}, "fallback_url": url,
                "image_path": have_img,
            })
            total += 1
            print(f"  [{region}] {title[:40]}")
    print(f"done, {total} France estate listings")


if __name__ == "__main__":
    main()
