#!/usr/bin/env python3
"""Invaluable live-auction lot puller for ART, via the keyless Jina render.

Jina server-side renders Invaluable's search into clean Markdown with real,
current lot cards: title (in the image alt / link text), auction-lot URL, house,
estimate pair, and the current bid with buyer's premium and bid count. Because
Jina renders LIVE, the prices are current — not stale snapshots.

Works (and is currency-aware: AUD/USD/GBP/EUR figures all carry their code.
Fetch first, then FETCH_PROVIDER=jina for the render.
"""
import re, sys, os
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

# fine-art live search (site's own query shape)
SEARCH_URL = ("https://www.invaluable.com/search/?q=painting&auctionType=live")

CURR = re.compile(r"(\d[\d,]*(?:\.\d{1,2})?)\s*(AUD|USD|GBP|EUR|CAD|CHF|HKD)\b", re.I)
EST = re.compile(r"Est(?:\.)?:?\s*([^(\n]{2,45})", re.I)
BIDS = re.compile(r"(\d+)\s*bids", re.I)
ART_KW = re.compile(r"(painting|work|oil|watercolour|watercolor|etching|print|"
                    r"drawing|sculpture|bronze|still|landscape|poster|portrait|"
                    r"art|piece|canvas|board|montage|engraving|gouache|acrylic|"
                    r"aquatint|lithograph|ink|pencil|charcoal|nude|portrait|ink)", re.I)
# things that are NOT art even if they contain an art keyword
NOT_ART = re.compile(r"(watch|jewel|ring|diamond|bracelet|necklace|pendant|parure|"
                     r"sideboard|cabinet|chair|table|rug|carpet|door|sideboard|"
                     r"furniture|vase|porcelain|bond|currency|coin|postage|car|"
                     r"autograph|memorabilia|parity|badge|sneaker|jacket)", re.I)

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def parse_amount(tup):
    if not tup:
        return None, None
    num, code = tup
    num = num.replace(",", "")
    try:
        return int(float(num) * 100), code.upper()
    except ValueError:
        return None, None

def main():
    con = db.connect("data/harvest.db")
    if os.environ.get("FETCH_PROVIDER", "direct") != "jina":
        print("note: set FETCH_PROVIDER=jina for this puller (keyless live render)")
    try:
        md = fetch.get(SEARCH_URL, recover=True)
    except Exception as e:
        print("FAIL", e)
        return
    # each lot card: image-alt carries the title, then the auction-lot link, then
    # house + estimate + current bid. Cards are joined by 'Days Left' + '[Image'
    txt = clean(md)
    # split into cards on the 'Days Left' boundary or by the auction-lot link
    lots = []
    # find title -> url -> footer triples: "BID-ctx" pattern per card
    # we parse the whole text for: title(alt) ... url ... house ... Est ... bid
    cards = re.split(r"(?=\[!\[Image \d*:)", txt)
    for card in cards:
        if not ART_KW.search(card) or NOT_ART.search(card):
            continue
        # title: from image alt or first bracketed text with enough length
        title_m = re.search(r"!\[Image \d*: ([^\]]{8,160})\]",
                            card) or re.search(r"\* \[([^\]]{8,160})\]",
                                               card)
        url_m = re.search(r"https://www\.invaluable\.com/auction-lot/[^\s)\]]+",
                          card)
        if not title_m or not url_m:
            continue
        title = clean(title_m.group(1))
        url = url_m.group(0)
        # house = a line like 'Lawsons' / 'Santa Fe Art Auction' before 'Est'
        house_m = re.search(r"\]\s*~*\s*([A-Z][A-Za-z0-9 &'.,-]{2,40})\.?\s+Est(?:\.)?:", card)
        house = clean(house_m.group(1)) if house_m else None
        est_m = EST.search(card)
        est = clean(est_m.group(1)) if est_m else None
        # current bid = the standalone $ figure BETWEEN the estimate range and
        # the 'Incl. <BP>' buyer's-premium note (the actual hammer/current bid).
        current_amt, current_cur = None, None
        bid_seg = re.search(r"Est(?:\.)?:.*?-\s*[\d,]+[^I]{0,8}?\$\s*([\d,]+(?:\.\d{1,2})?)", card)
        if bid_seg:
            try:
                current_amt = int(float(bid_seg.group(1).replace(",", "")) * 100)
                current_cur = "USD"
            except ValueError:
                pass
        if current_amt is None:
            m_usd = re.search(r"\(\$([\d,]+(?:\.\d{1,2})?)\)", card)
            if m_usd:
                try:
                    current_amt = int(float(m_usd.group(1).replace(",", "")) * 100)
                    current_cur = "USD"
                except ValueError:
                    pass
        if not est or len(est) < 3:
            est = None
        bids = BIDS.search(card)
        rec = {
            "dept": "art", "source": "invaluable.com",
            "url": url,
            "title": title,
            "ask_cents": current_amt, "currency": current_cur or "USD",
            "condition": None,
            "spec": {"house": house, "estimate": est, "estimate_raw": est,
                     "bids": bids.group(1) if bids else None},
            "fallback_url": ("https://www.invaluable.com/search/?q=painting"),
        }
        db.upsert(con, rec)
        lots.append(rec)
    print(f"inserted {len(lots)} art lots")

if __name__ == "__main__":
    main()
