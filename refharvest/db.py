import json, os, sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS items(
  id INTEGER PRIMARY KEY,
  dept TEXT, source TEXT, url TEXT UNIQUE, title TEXT,
  ask_cents INTEGER, currency TEXT, condition TEXT,
  spec_json TEXT, fallback_url TEXT, image_path TEXT,
  state TEXT DEFAULT 'live', fallback_active INTEGER DEFAULT 0,
  first_seen TEXT, last_checked TEXT, last_seen_cents INTEGER,
  s_value REAL, s_quality REAL, s_desirability REAL,
  rank INTEGER, notes TEXT
);
CREATE TABLE IF NOT EXISTS link_events(
  id INTEGER PRIMARY KEY, item_id INTEGER, ts TEXT, status TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY, ts TEXT, mode TEXT, target TEXT, ok INTEGER, detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_state ON items(state);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path="data/harvest.db"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def upsert(con, rec):
    cur = con.execute("SELECT id FROM items WHERE url = ?", (rec["url"],))
    row = cur.fetchone()
    if row:
        con.execute(
            "UPDATE items SET title=?, ask_cents=?, currency=?, condition=?,"
            " spec_json=?, fallback_url=?, last_checked=? WHERE id=?",
            (rec.get("title"), rec.get("ask_cents"), rec.get("currency"),
             rec.get("condition"), json.dumps(rec.get("spec") or {}),
             rec.get("fallback_url"), now(), row["id"]))
        con.commit()
        return row["id"]
    cur = con.execute(
        "INSERT INTO items(dept,source,url,title,ask_cents,currency,condition,"
        "spec_json,fallback_url,first_seen,last_checked)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (rec.get("dept"), rec.get("source"), rec["url"], rec.get("title"),
         rec.get("ask_cents"), rec.get("currency"), rec.get("condition"),
         json.dumps(rec.get("spec") or {}), rec.get("fallback_url"),
         now(), now()))
    con.commit()
    return cur.lastrowid


def event(con, item_id, status, note=""):
    con.execute("INSERT INTO link_events(item_id,ts,status,note) VALUES(?,?,?,?)",
                (item_id, now(), status, note))
    con.commit()


def run_log(con, mode, target, ok, detail=""):
    con.execute("INSERT INTO runs(ts,mode,target,ok,detail) VALUES(?,?,?,?,?)",
                (now(), mode, target, int(ok), detail[:400]))
    con.commit()


def export(con, path):
    rows = con.execute(
        "SELECT * FROM items WHERE rank IS NOT NULL ORDER BY dept, rank").fetchall()
    out = []
    for r in rows:
        live = r["state"] == "live" and not r["fallback_active"]
        out.append({
            "dept": r["dept"], "rank": r["rank"], "title": r["title"],
            "ask": (r["ask_cents"] or 0) / 100 or None,
            "currency": r["currency"], "condition": r["condition"],
            "scores": {"value": r["s_value"], "quality": r["s_quality"],
                       "desirability": r["s_desirability"]},
            "link": r["url"] if live else (r["fallback_url"] or r["url"]),
            "link_state": "live" if live else "fallback",
            "last_seen": (r["last_seen_cents"] or 0) / 100 or None,
            "image": r["image_path"], "spec": json.loads(r["spec_json"] or "{}"),
        })
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    return len(out)