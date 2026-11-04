#!/usr/bin/env python3
"""Cache listing images locally. Referer set to the source host."""
import argparse, hashlib, mimetypes, os
from urllib.parse import urlparse
import requests
import db

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/harvest.db")
    ap.add_argument("--dir", default="media")
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()

    os.makedirs(a.dir, exist_ok=True)
    con = db.connect(a.db)
    rows = con.execute(
        "SELECT id,url,image_path FROM items WHERE image_path IS NULL "
        "AND state='live' LIMIT ?", (a.limit,)).fetchall()

    for r in rows:
        src = r["url"]
        try:
            resp = requests.get(src, headers={"User-Agent": UA,
                                              "Referer": f"{urlparse(src).scheme}://"
                                                         f"{urlparse(src).netloc}"},
                                timeout=30)
            resp.raise_for_status()
            ext = (mimetypes.guess_extension(
                resp.headers.get("Content-Type", "").split(";")[0]) or ".jpg")
            name = hashlib.sha1(src.encode()).hexdigest()[:16] + ext
            path = os.path.join(a.dir, name)
            open(path, "wb").write(resp.content)
            con.execute("UPDATE items SET image_path=? WHERE id=?", (path, r["id"]))
            con.commit()
            print("ok", path)
        except Exception as e:                       # noqa: BLE001
            print("fail", src, e)


if __name__ == "__main__":
    main()