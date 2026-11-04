#!/usr/bin/env python3
"""Guns.com live-firearms puller (FIELD), via the keyless Jina render.

Guns.com is a JS SPA behind a bot wall; direct fetch gets a shell. Jina renders
category pages into Markdown where each firearm card is a single markdown link:

  [<flags> <TITLE> ![Image N: <TITLE>](https://images.guns.com/prod/...jpg)
   NEW $<price> was $<was>](https://www.guns.com/firearms/p/<slug>?i=<id> "<TITLE>")

So parse the whole card link: title from the quoted link-title, product image
from the images.guns.com/prod URL, price from the inner $ figure. Field dept.
Run with FETCH_PROVIDER=jina.
"""
import re, sys, os
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

# shotguns + a shotgun-price-sorted page for a healthy live field feed
PAGES = [
    "https://www.guns.com/firearms/shotguns",
    "https://www.guns.com/firearms/shotguns?pg=2",
    "https://www.guns.com/firearms/shotguns?pg=3",
]
# whole card: [<anything> ![[alt](img) ... ](<product url...> "<link title>")
CARD = re.compile(
    r"\[([^\]]*)\!\[[^\]]*\]\((https://images\.guns\.com/prod/[^)\s]+)"
    r"(.*?)\]\((https://www\.guns\.com/firearms/p/[^)\s]+(?:\?[^)\s]*)?)"
    r"(?:\s+\"([^\"]*)\")?\)", re.S)
# price: the $ figure inside the card text (current ask, not the 'was')
PRICE = re.compile(r"\$\s?([\d][\d,]*(?:\.\d{1,2})?)")
WAS = re.compile(r"was\s+\$[\d,]+")


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main():
    con = db.connect("data/harvest.db")
    if os.environ.get("FETCH_PROVIDER", "direct") != "jina":
        print("note: set FETCH_PROVIDER=jina for this puller")
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
        for m in CARD.finditer(body):
            inner, img, tail, url = m.group(1), m.group(2), m.group(3), m.group(4)
            title = clean(m.group(5)) if m.group(5) else clean(inner)
            pm = PRICE.findall(tail)
            ask = None
            # last $ figure is today's price; skip a 'was $X' row
            if pm:
                try:
                    ask = int(float(pm[0].replace(",", "")) * 100)
                except ValueError:
                    pass
            rec = {
                "dept": "field", "source": "guns.com",
                "url": url, "title": title[:160],
                "ask_cents": ask, "currency": "USD", "condition": "New",
                "spec": {}, "fallback_url": page,
                "image_path": img,
            }
            db.upsert(con, rec)
            n += 1
        print(f"[{page}] +{n} firearms")
        total += n
    print(f"done, {total} Guns.com items this run")


if __name__ == "__main__":
    main()
