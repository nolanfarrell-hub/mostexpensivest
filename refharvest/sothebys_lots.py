#!/usr/bin/env python3
"""Sotheby's handbags/art live-lot puller.
Card anatomy (from structure harvest): a card contains h5 (brand), a title <p>,
and a price <p> with the figure inline ("30,800 USD"). The generic extractor
flattens these into one string and its price regex skips mid-line figures, so we
pull with explicit selectors instead.
Writes into the harvest DB as field-less handbag lots (dept=style)."""
import re, sys, time
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
from bs4 import BeautifulSoup
import db, fetch

URLS = {
    "style": "https://www.sothebys.com/en/buy/handbags",
}
PRICE = re.compile(r"\$?\s?([\d,]+)\s*USD", re.I)

def money_cents(text):
    m = PRICE.search(text or "")
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", "")) * 100
    except ValueError:
        return None

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def main():
    con = db.connect("data/harvest.db")
    total = 0
    for dept, url in URLS.items():
        try:
            html = fetch.get(url, render=True)
        except Exception as e:
            print(f"[{dept}] FAIL {e}")
            continue
        soup = BeautifulSoup(html, "lxml")
        cards = soup.find_all("div", recursive=True)
        # find the tiniest article/card blocks that contain an h5 brand + price
        seen = set()
        n = 0
        for c in cards:
            if c.find("img") is None:
                continue
            h5 = c.find("h5")
            if not h5:
                continue
            # narrow to the smallest container holding brand + a price <p>
            p_price = c.find("p", string=PRICE)
            if not p_price:
                continue
            title = c.find("p")
            # title is the p that is NOT the price p and not empty; take the
            # text of the card minus brand+price lines.
            brand = clean(h5.get_text())
            # the title p sits right after the h5 in anatomy
            nxt = h5.find_next("p")
            t = clean(nxt.get_text()) if nxt else ""
            key = brand + t
            if not t or key in seen:
                continue
            seen.add(key)
            cents = money_cents(p_price.get_text())
            img_el = c.find("img")
            sock = ""
            if img_el is not None:
                # real photo is in data-src (lazy-load); src is often a placeholder
                sock = (img_el.get("data-src") or img_el.get("src") or "")
                if sock.startswith("data:"):   # placeholder SVG — skip
                    sock = ""
            rec = {
                "dept": dept, "source": "www.sothebys.com",
                "url": url + "#" + re.sub(r"\W+", "_", key)[:40],
                "title": f"{brand} · {t}",
                "ask_cents": cents, "currency": "USD",
                "condition": None,
                "spec": {"brand": brand, "label": t[:80]},
                "fallback_url": "https://www.sothebys.com/en/buy/handbags",
                "image_path": sock or None,
            }
            db.upsert(con, rec)
            n += 1
        print(f"[{dept}] +{n} items")
        total += n
        time.sleep(3)
    print(f"done, {total} Sotheby's items this run")

if __name__ == "__main__":
    main()
