#!/usr/bin/env python3
"""Holt's live-lot puller. The lot-search endpoint serves clean past-sale cards:
   <div class="row p-2 bg-white border rounded"> with h5 'Lot NNNN', date span,
   description, then 'Sold for GBP x' / 'Unsold' and an estimate pair.
Bore, provenance and hammer-vs-estimate are the commodity of axes 2 & 3, so this
parses them into the harvest DB (state='live' feed, hammer/estimate ratio in spec
for the scorer)."""
import re, sys, time
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
from bs4 import BeautifulSoup
import db, fetch

LIVE_SALES = ["S0826", "A0726"]  # re-discover from /auctions.asp if 0 lots

MONEY = re.compile(r"([\u00a3$\u20ac])\s*([\d,]+)")

def num(s):
    try:
        return int(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None

def main():
    con = db.connect("data/harvest.db")
    total = 0
    for sale in LIVE_SALES:
        url = (f"https://www.holtsauctioneers.com/asp/searchresults.asp"
               f"?pg=1&ps=250&st=D&subs_value=0&sale_no={sale}")
        try:
            html = fetch.get(url)
        except Exception as e:
            print(f"[{sale}] FAIL {e}")
            continue
        soup = BeautifulSoup(html, "lxml")
        cards = soup.find_all("div", class_="border",
                               recursive=True)
        # filter to real lot cards: contain an h5 'Lot NNNN'
        lots = 0
        seen = set()
        for c in cards:
            h5 = c.find("h5")
            if not h5 or not re.match(r"Lot\s+\d{3,4}", h5.get_text(strip=True)):
                continue
            ## avoid re-climbing ancestors of the same card
            txt = re.sub(r"\s+", " ", c.get_text("\n", strip=True))
            m = re.search(r"Lot (\d{3,4})\s+(\d{1,2} [A-Za-z]{3} \d{4})", txt)
            if not m:
                continue
            key = m.group(1)
            if key in seen:
                continue
            seen.add(key)
            desc = txt
            for piece in ["Full Description", "Sold for", "Unsold",
                          m.group(2)]:
                desc = desc.replace(piece, " ", 1)
            desc = re.sub(r"\s+", " ", desc).strip()
            if len(desc) < 12:
                continue
            hit_m = MONEY.search(txt.split("Sold for", 1)[1]) if "Sold for" in txt else None
            est_m = re.search(r"([\d,]+)\s*-\s*([\d,]+)", txt)
            sold = "Sold for" in txt
            ask = num(hit_m.group(2)) * 100 if (sold and hit_m) else \
                  (num(est_m.group(1)) * 100 if est_m else None)
            ratio = None
            if sold and hit_m and est_m:
                mid = (num(est_m.group(1)) + num(est_m.group(2))) / 2
                if mid:
                    ratio = round(num(hit_m.group(2)) / mid, 3)
            rec = {
                "dept": "field", "source": "holtsauctioneers.com",
                "url": url + f"#lot{m.group(1)}", "title": f"{desc[:150]}",
                "ask_cents": ask,
                "currency": "GBP",
                "condition": None,
                "spec": {"lot": m.group(1), "date": m.group(2),
                         "sold": sold, "hammer_to_est": ratio,
                         "est_low": num(est_m.group(1)) if est_m else None,
                         "est_high": num(est_m.group(2)) if est_m else None},
                "fallback_url": ("https://www.holtsauctioneers.com/"
                                 "asp/searchresults.asp?st=D&sale_no=" + sale),
            }
            db.upsert(con, rec)
            lots += 1
        print(f"[{sale}] +{lots} lots")
        total += lots
        time.sleep(3)
    print(f"done, {total} Holt's lots this run")

if __name__ == "__main__":
    main()
