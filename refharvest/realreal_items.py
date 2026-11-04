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

# URL pattern for product-images.therealreal.com (main product image)
PROD_IMG = re.compile(r"https://product-images\.therealreal\.com/[A-Z0-9]+_1_enlarged\.jpg")

# The RealReal reports current sale price + original. Grab the ACTUAL ask (the
# last $ figure, which is today's price), not the struck-through original.
ASK = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)\s?$", re.M)
CURR = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
COND = re.compile(r"Condition:\s*([A-Za-z ]+)", re.I)
SIZE = re.compile(r"Size\s*([^\s,|]+)")

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def fetch_own_image(product_url):
    """Fetch a product page and return its first product-image URL, or None."""
    try:
        page_html = fetch.get(product_url, recover=True)
        m = PROD_IMG.search(page_html)
        if m:
            return m.group(0)
    except Exception:
        pass
    return None

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
        # Build image-by-product-url map from [![alt](img)](product_url) pairs.
        # This is the most reliable matching — each image is explicitly linked
        # to its product URL on the listing page.
        img_by_url = {}
        for m in re.finditer(
            r"!\[Image \d+:\s*([^\]]*)\]\s*\(\s*([^)]*)\s*\)\s*\]\s*\(\s*([^)]*)\s*\)",
            md,
        ):
            iu = m.group(2).strip()
            pu = m.group(3).strip()
            if pu.startswith("http") and "products.therealreal.com" not in pu:
                img_by_url[pu] = iu
        n = 0
        for name, url, title, rest in blocks:
            name = clean(name); title = clean(title)
            if not title or not url:
                continue
            # 1) Exact URL match — best: the listing page links the image to
            #    this product's URL
            img_url = img_by_url.get(url)
            # 2) Fallback: image appears in this block's rest (closest match
            #    by document position)
            if not img_url:
                rest_img = PROD_IMG.search(rest)
                if rest_img:
                    img_url = rest_img.group(0)
            # 3) If still no image, try product-page fetch for orphan items
            #    (already in DB but imageless, or newly seen).
            if not img_url:
                img_url = fetch_own_image(url)
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
                "image_path": img_url,
            }
            db.upsert(con, rec)
            n += 1
        print(f"[{url}] +{n} items (dept {dept})")
        total += n
    # Post-processing: backfill images for any existing imageless RealReal items
    # that weren't on the current listing page (e.g. rotated out but still
    # in the feed). Fetch each product page individually for its own image.
    orphans = con.execute(
        "SELECT id, url FROM items WHERE dept='style' AND source='therealreal.com'"
        " AND image_path IS NULL"
    ).fetchall()
    for oid, ourl in orphans:
        img_url = fetch_own_image(ourl)
        if img_url:
            con.execute("UPDATE items SET image_path=? WHERE id=?", (img_url, oid))
            con.commit()
            print(f"  backfilled image for [{ourl}]")
    print(f"done, {total} RealReal items this run")
    if orphans:
        still_orphans = con.execute(
            "SELECT count(*) FROM items WHERE dept='style' AND source='therealreal.com'"
            " AND image_path IS NULL"
        ).fetchone()[0]
        print(f"  imageless after backfill: {still_orphans}")

if __name__ == "__main__":
    main()