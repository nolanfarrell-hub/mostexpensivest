#!/usr/bin/env python3
"""Vestiaire Collective live-men's puller (STYLE), via the keyless Jina render.

Each men's card is a SINGLE markdown link whose link-text carries everything:

  [![Image N](https://images.vestiairecollective.com/.../produit/<slug>-<id>-1_2.jpg)
   ### BRAND Item  Size:...  $<price>  United States](https://us.vestiairecollective.com/men-clothing/<cat>/<brand>/<slug>-<id>.shtml)

Regex the whole card: `[![img](...)<text>](url.shtml)`. The image filename
embeds the same <id> as the URL. Run with FETCH_PROVIDER=jina.
"""
import re, sys, os
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

PAGES = [
    "https://us.vestiairecollective.com/men/",
]
# whole card: leading image markdown, then the inner text, then the url
CARD = re.compile(
    r"\[!\[[^\]]*\]\((https://images\.vestiairecollective\.com/[^)]*?/produit/[^)]*?)-(\d+)-1_\d\.jpg\)"
    r"(.*?)\]\((https://us\.vestiairecollective\.com/[^)]*\.shtml)\)",
    re.S)
PRICE = re.compile(r"([$€£])\s?([\d][\d,]*(?:\.\d{1,2})?)")
BRAND = re.compile(r"###\s*([A-Z][A-Z &'-]{1,30})")


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
            img_url, pid, rest, prod_url = m.group(1), m.group(2), m.group(3), m.group(4)
            text = clean(re.sub(r"!\[[^\]]*\]\([^)]*\)", "", rest)).lstrip("#").strip()
            bm = BRAND.search(rest)
            title = text or (bm.group(1) if bm else "")
            pm = PRICE.search(rest)
            ask, cur = None, None
            if pm:
                code = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}.get(pm.group(1))
                try:
                    ask = int(float(pm.group(2).replace(",", "").replace("\u00a0", "")) * 100)
                    cur = code
                except ValueError:
                    pass
            db.upsert(con, {
                "dept": "style", "source": "vestiairecollective.com",
                "url": prod_url, "title": title[:160],
                "ask_cents": ask, "currency": cur, "condition": None,
                "spec": {}, "fallback_url": page, "image_path": img_url,
            })
            n += 1
        print(f"[{page}] +{n} men's items")
        total += n
    print(f"done, {total} Vestiaire men's items this run")


if __name__ == "__main__":
    main()
