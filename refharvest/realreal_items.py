#!/usr/bin/env python3
"""The RealReal live-lot puller for STYLE, via the Jina keyless render route.

Jina (r.jina.ai) server-side renders the page and returns the items as clean
Markdown — bypassing the Cloudflare wall WITHOUT a snapshot, so prices are live
and current. Each item block: [Brand](product-url) Title / Size line /
Condition: X / price (current ask, with est-retail or was-price where shown).

Fetch via FETCH_PROVIDER=jina (keyless low-volume) then recover=True.
"""
import re, sys, os
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

PAGES = {"https://www.therealreal.com/shop/women": "style"}

# The RealReal reports current sale price + original. Grab the ACTUAL ask (the
# last $ figure, which is today's price), not the struck-through original.
ASK = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)\s?$", re.M)
CURR = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
COND = re.compile(r"Condition:\s*([A-Za-z ]+)", re.I)
SIZE = re.compile(r"Size\s*([^\s,|]+)")

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def main():
    con = db.connect("data/harvest.db")
    if os.environ.get("FETCH_PROVIDER", "direct") != "jina":
        print("note: set FETCH_PROVIDER=jina for this puller (keyless live render)")
    total = 0
    for url, dept in PAGES.items():
        try:
            html = fetch.get(url, recover=True)
        except Exception as e:
            print(f"[{url}] FAIL {e}")
            continue
        md = html[html.find("Markdown Content:") + len("Markdown Content:"):] \
             if "Markdown Content:" in html else html
        blocks = re.findall(
            r"\[([^\]]+)\]\(([^)]*products[^)]*)\)\s*([^\n]+)\n(.*?)(?=\n\[[A-Z]|\n\Z)",
            md, re.S)
        n = 0
        for name, url, title, rest in blocks:
            name = clean(name); title = clean(title)
            if not title or not url:
                continue
            # price = the last $ figure in the block (today's sale price)
            ask_fig = CURR.findall(rest)
            ask = None
            if ask_fig:
                try:
                    ask = int(float(ask_fig[-1].replace(",", "")) * 100)
                except ValueError:
                    ask = None
            cond_m = COND.search(rest)
            size_m = SIZE.search(rest)
            rec = {
                "dept": dept, "source": "therealreal.com",
                "url": url,
                "title": f"{name} · {title}",
                "ask_cents": ask, "currency": "USD",
                "condition": cond_m.group(1).strip() if cond_m else None,
                "spec": {"brand": name, "size": size_m.group(1) if size_m else None,
                         "excerpt": rest[:200]},
                "fallback_url": "https://www.therealreal.com/shop/women",
            }
            db.upsert(con, rec)
            n += 1
        print(f"[{url}] +{n} items (dept {dept}) · ask-filled {sum(1 for _ in () )}")
        total += n
    print(f"done, {total} RealReal items this run")

if __name__ == "__main__":
    main()
