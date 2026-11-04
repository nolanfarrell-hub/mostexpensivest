#!/usr/bin/env python3
"""JamesEdition luxury-estate puller (ESTATES), via the keyless Jina render.

JamesEdition is a JS-heavy SPA behind a bot wall; direct fetch gets a flush
page, not the listings. Jina server-side renders /real_estate/all into Markdown
where each listing is a link to a `real_estate/...` URL carrying the title and
price text. Only a few promoted cards embed their thumbnail inline — most cards
lazy-load and Jina's render drops the image.

Reliable image path: the listing DETAIL page (also via Jina) always exposes the
hero `listing_images/...jpg`. So: parse index cards for url/title/price + any
inline image, and for any listing still missing an image, fetch its detail page
and take the first `listing_images/...` thumbnail.

Upserts are idempotent on url. Run with FETCH_PROVIDER=jina.
"""
import re, sys, os, time
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

SEARCH_URL = "https://www.jamesedition.com/real_estate/all"

# listing card link: [card text...](real_estate_url "Title")
# NOTE: agency/agent pages share the real_estate/ path segment (offices/real_estate/...,
# agents/...); only match actual /real_estate/<slug> listing URLs.
LINK = re.compile(r"\[(.*?)\]\((https://www\.jamesedition\.com/real_estate/[^)/\s]+/[^)\s]+)"
                  r"(?:\s+\"[^\"]*\")?\)", re.S)
# inline listing-image URL inside card text (skip dealer/agent logos)
IMG = re.compile(r"!\[[^\]]*\]\((https://img\.jamesedition\.com/listing_images/[^)\s]+)")
TITLE_ALT = re.compile(r"!\[Image \d+: ([^\]\(]{6,160})\]\s*\(https://img\.jamesedition\.com/listing_images/")
CURR = re.compile(r"([$€£])\s*([\d,]+(?:\.[\d,]+)?)")
# the hero image on a detail page (first real listing thumbnail)
HERO = re.compile(r"https://img\.jamesedition\.com/listing_images/[^)\s\"']+")
# navigate the index: '...map...' marker separates the promoted rail from the grid
GRID = "Show all results on map"


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def amount(text):
    m = CURR.search(text or "")
    if not m:
        return None, None
    try:
        return int(float(m.group(2).replace(",", "")) * 100), \
            {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}.get(m.group(1))
    except ValueError:
        return None, None


def main():
    con = db.connect("data/harvest.db")
    if os.environ.get("FETCH_PROVIDER", "direct") != "jina":
        print("note: set FETCH_PROVIDER=jina for this puller")
    try:
        md = fetch.get(SEARCH_URL, recover=True)
    except Exception as e:            # noqa: BLE001
        print("FAIL index", e)
        return

    # group card link blocks by real_estate url (a listing can span two links)
    by_url = {}
    for m in LINK.finditer(md):
        text, url = m.group(1), m.group(2)
        if "page=" in url or url.endswith("#"):
            continue
        by_url.setdefault(url, []).append(text)

    lots = 0
    for url, blocks in by_url.items():
        joined = "\n".join(blocks)
        im = IMG.search(joined)          # inline thumbnail, if the card has one
        img_url = im.group(1) if im else None
        ta = TITLE_ALT.search(joined)
        title = clean(ta.group(1)) if ta else clean(joined)[:120] or url.rsplit("/", 1)[-1]
        # alt titles carry a trailing image-counter ('Villa in X 1'); drop it
        title = re.sub(r"\s+\d+$", "", title).strip() or title
        # a listing not re-carried inline must not lose its stored image
        cur = con.execute("SELECT image_path FROM items WHERE url=?", (url,)).fetchone()
        have_img = img_url or (cur and cur["image_path"])
        ask, cur2 = amount(re.sub(r"!\[[^\]]*\]\([^)]*\)", "", joined))
        rec = {
            "dept": "estates", "source": "www.jamesedition.com",
            "url": url, "title": title[:200],
            "ask_cents": ask, "currency": cur2, "condition": None,
            "spec": {}, "fallback_url": SEARCH_URL, "image_path": have_img,
        }
        db.upsert(con, rec)
        lots += 1
        # detail-page fallback — only when we genuinely still lack an image
        if not have_img:
            try:
                dmd = fetch.get(url)      # jina render of the listing detail
                hero = HERO.search(dmd)
                if hero:
                    rec["image_path"] = hero.group(0)
                    db.upsert(con, rec)
                    print(f"  +img {url.rsplit('/', 1)[-1][:34]}")
                time.sleep(0.75)          # be gentle on jina for the fallback loop
            except Exception as e:        # noqa: BLE001
                print(f"  detail fail {url.rsplit('/', 1)[-1][:30]} {e}")
    print(f"inserted {lots} estate listings")


if __name__ == "__main__":
    main()
