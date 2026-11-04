#!/usr/bin/env python3
"""Grailed live-men's-streetwear puller (STYLE), via the keyless Jina render.

Grailed is a JS SPA behind a bot wall; direct fetch gets a shell. Jina renders
/shop/outerwear (and friends) into Markdown where each listing card is:

  [![Image N: <full title>](https://media-assets.grailed.com/prd/listing/...?)
   <relative time> <brand> l <title>](https://www.grailed.com/listings/<id>-...)
  $<price>

So: the listing URL carries the id, the image alt carries the title, and the
price sits on the following line. Run with FETCH_PROVIDER=jina.
"""
import re, sys, os
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

# men's streetwear / luxury — a spread of categories for a healthy mix
PAGES = [
    "https://www.grailed.com/shop/outerwear",
    "https://www.grailed.com/shop/knitwear",
    "https://www.grailed.com/shop/denim",
]
# card: [![...](img) ...blah ...title](listing_url)
CARD = re.compile(
    r"\[!\[[^\]]*\]\((https://media-assets\.grailed\.com/[^)\s?]+)[^)]*\)"
    r"[^\]]*\]\((https://www\.grailed\.com/listings/[^) \n]+)", re.S)
PRICE = re.compile(r"\$([\d,]+(?:\.[\d,]+)?)\s*$", re.M)
TITLE = re.compile(r"!\[Image \d+: ([^\]]{8,120})\]")


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main():
    con = db.connect("data/harvest.db")
    if os.environ.get("FETCH_PROVIDER", "direct") != "jina":
        print("note: set FETCH_PROVIDER=jina for this puller (keyless live render)")
    total = 0
    for page in PAGES:
        try:
            html = fetch.get(page, recover=True)
        except Exception as e:            # noqa: BLE001
            print(f"[{page}] FAIL {e}")
            continue
        body = html[html.find("Markdown Content:")+len("Markdown Content:"):] \
               if "Markdown Content:" in html else html
        n = 0
        # split into blocks on each listing card start
        starts = [m.start() for m in CARD.finditer(body)]
        for k, m in enumerate(CARD.finditer(body)):
            img, url = m.group(1), m.group(2)
            # card block extends to the next card or ~3 lines (price line)
            end = starts[k+1] if k+1 < len(starts) else len(body)
            block = body[m.end():end]
            pm = PRICE.search(block)
            ta = TITLE.search(m.group(0))
            title = clean(ta.group(1)) if ta else url.rsplit("/", 1)[-1][:60]
            ask = None
            if pm:
                try:
                    ask = int(float(pm.group(1).replace(",", "")) * 100)
                except ValueError:
                    pass
            rec = {
                "dept": "style", "source": "grailed.com",
                "url": url, "title": title[:160],
                "ask_cents": ask, "currency": "USD", "condition": None,
                "spec": {}, "fallback_url": page,
                "image_path": img,
            }
            db.upsert(con, rec)
            n += 1
        print(f"[{page}] +{n} men's listings")
        total += n
    print(f"done, {total} Grailed items this run")


if __name__ == "__main__":
    main()
