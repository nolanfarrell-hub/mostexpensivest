#!/usr/bin/env python3
"""Bond Roberts cigar puller for dept='table'.

Product pages: https://bondroberts.com/product/view/<id>/<slug>
Bond Roberts serves JS-rendered content; the direct request 403s from our
runtime (LibreSSL handshake), so we route through Jina (FETCH_PROVIDER=jina),
which server-renders the page and returns markdown with real product images.

Image source: CloudFront CDN
  https://d2urds79hdtjl7.cloudfront.net/uploads/product/compressed/file_upload-*.jpeg

The puller reads the 10 known product URLs from the DB, fetches each page,
extracts the clean title, current bid price, and first product image, then
upserts back to the DB — idempotent on url."""

import os, re, sys, time
sys.path.insert(0, "/Users/nolanfarrell/sites/mostexpensivest/refharvest")
import db, fetch

# Image URL pattern: CloudFront CDN with /uploads/product/compressed/
CLOUDFRONT = re.compile(
    r"https://d2urds79hdtjl7\.cloudfront\.net/uploads/product/compressed/[^\"')\s]+"
)

# Bid price: "Current Bid\n#### $321.00 US"
BID = re.compile(r"Current\s*Bid\s*\n\s*####\s*\$?([\d,]+\.\d{2})", re.I)


def num_price(s):
    """Parse '$1,205.00' -> 120500 (cents)."""
    try:
        return int(float(s.replace(",", "")) * 100)
    except (ValueError, TypeError, AttributeError):
        return None


def parse_page(html, url):
    """Extract (title, bid_cents, image_url) from Jina-rendered markdown."""
    # Title is the first ## heading that is NOT the cookie/consent text
    title = None
    for m in re.finditer(r"^## (.+)", html, re.M):
        cand = m.group(1).strip()
        # Skip cookie/consent/placeholder headings
        if cand.lower().startswith("this website is using cookies"):
            continue
        if cand.lower().startswith("are you old enough"):
            continue
        if len(cand) > 5 and cand != "Storage Conditions":
            title = cand
            break

    # Bid price
    bid_m = BID.search(html)
    bid_cents = num_price(bid_m.group(1)) if bid_m else None

    # First real product image (skip site chrome icons: usFlag/svg/logo)
    image_url = None
    for m in CLOUDFRONT.finditer(html):
        image_url = m.group(0)
        break  # first product image only

    return title, bid_cents, image_url


def main():
    # Ensure FETCH_PROVIDER=jina is set
    if os.environ.get("FETCH_PROVIDER", "direct") != "jina":
        print("WARNING: FETCH_PROVIDER not set to jina; bondroberts.com "
              "blocks direct requests. Run with: FETCH_PROVIDER=jina")
        # Still try; fetch.py will fall through to direct which will 403.

    con = db.connect("data/harvest.db")

    # Read all known Bond Roberts product URLs from the DB
    rows = con.execute(
        "SELECT id, url, title, image_path FROM items "
        "WHERE dept='table' AND source='www.bondroberts.com' "
        "ORDER BY id"
    ).fetchall()

    if not rows:
        print("No Bond Roberts products found in DB (dept=table).")
        return

    print(f"Found {len(rows)} Bond Roberts products in DB.")
    updated = 0
    skipped = 0
    errors = 0

    for row in rows:
        url = row["url"]
        # Use the raw bondroberts.com URL (Jina will redirect to www)
        # or the www version — either works with Jina
        fetch_url = url

        try:
            html = fetch.get(fetch_url)
        except Exception as e:
            print(f"  FAIL fetch: {e}")
            errors += 1
            continue

        if not html or len(html) < 500:
            print(f"  SKIP short body ({len(html) if html else 0} chars): {url}")
            errors += 1
            continue

        title, bid_cents, image_url = parse_page(html, url)

        if not title:
            print(f"  SKIP no title parsed: {url}")
            errors += 1
            continue

        rec = {
            "url": url,
            "title": title,
            "ask_cents": bid_cents,
            "currency": "USD",
            "condition": None,
            "spec": {"source": "www.bondroberts.com"},
            "fallback_url": url,
            "image_path": image_url,
        }

        db.upsert(con, rec)
        img_status = "YES" if image_url else "none"
        print(f"  OK  id={row['id']:>4}  img={img_status:<6}  bid=${bid_cents//100 if bid_cents else '?':<8}  {title[:60]}")
        updated += 1
        time.sleep(1)  # be gentle

    print(f"\nDone. {updated} updated, {skipped} skipped, {errors} errors.")

    # Report final counts
    total = con.execute(
        "SELECT COUNT(*) FROM items WHERE dept='table' AND source='www.bondroberts.com'"
    ).fetchone()[0]
    with_img = con.execute(
        "SELECT COUNT(*) FROM items WHERE dept='table' AND source='www.bondroberts.com' AND image_path IS NOT NULL"
    ).fetchone()[0]
    print(f"DB: {total} total, {with_img} with images.")


if __name__ == "__main__":
    main()