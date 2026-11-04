#!/usr/bin/env python3
"""ME free comparables/rarity scorer.

Scores every item in the harvest DB on the three display axes (0-5, published
separately, never blended) using only data already in the DB — no paid index.

  Axis 1  cost/value   ask price + hammer-vs-estimate (market's own verdict)
  Axis 2  rarity       schedule frequency at the make/reference level
  Axis 3  investment   aggregate realised-vs-estimate (contested demand)

For items without a hammer/estimate record (live retail listings), axis 2 rarity
uses the condition/metadata the source published (box & papers, full set, limited)
and axis 3 falls back to source-level auction performance where available.

Output: writes scores into the DB columns s_value, s_quality, s_desirability,
maps to rank by dept (never blended — rank is only ordering), prints a summary.
"""
import json, re, sqlite3
from collections import defaultdict

def connect(path="data/harvest.db"):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con

def clamp(x, lo=0.0, hi=5.0):
    return max(lo, min(hi, round(x, 1)))

def maker_of(title):
    """Coarse make/reference key for rarity: leading proper-noun cluster."""
    t = re.sub(r"Lot \d+", "", title or "")
    t = re.sub(r"^(A |AN |THE |A |) ", "", t).strip()
    words = t.split(" ")
    key = " ".join(words[:3]).upper()
    return key

def main():
    con = connect()
    rows = con.execute("SELECT * FROM items").fetchall()

    # reference-level aggregates per DEPARTMENT (so rarity is comparable within
    # a dept's own market, not across unrelated depts)
    dept_rows = defaultdict(list)
    for r in rows:
        dept_rows[r["dept"]].append(r)

    # ---- per-dept rarity: rank-normalize reference frequency ----
    # The rarest reference in a dept scores 5, the most common scores based on
    # its share. A true inverse-frequency saturates (every singleton -> 5), so
    # instead we rank references by frequency: spread 5->~2 across the dept.
    rarity_by_key = {}
    sums = defaultdict(lambda: [0, 0])   # [sum_ratio, count] per reference, across all depts
    for dept, deptlist in dept_rows.items():
        freq = defaultdict(int)
        for r in deptlist:
            mk = maker_of(r["title"])
            freq[mk] += 1
            spec = json.loads(r["spec_json"] or "{}")
            ratio = spec.get("hammer_to_est")
            if ratio is not None:
                sums[mk][0] += ratio
                sums[mk][1] += 1
        if not freq:
            continue
        # unique reference keys, sorted by ascending frequency (rarest first)
        ordered = sorted(freq.items(), key=lambda kv: kv[1])
        n = len(ordered)
        # rank-based: first (rarest) gets 5, last (most common) gets ~2
        for i, (mk, c) in enumerate(ordered):
            if n == 1:
                rarity_by_key[mk] = 4.0
            else:
                frac = i / (n - 1)                 # 0 (rarest) .. 1 (common)
                rarity_by_key[mk] = clamp(5.0 - 2.6 * frac, 2.0, 5.0)
        # condition bonus handled in the item loop (not here)

    def rarity_score(mk):
        return rarity_by_key.get(mk, 3.0)

    def invest_score(mk):
        s, c = sums[mk]
        if c == 0:
            return 3.0  # no auction history -> neutral
        avg = s / c
        # avg 0.7 -> 1, avg 1.0 -> 3, avg 1.3+ -> 5 (contested demand)
        return clamp((avg - 0.55) * (5.0 / 0.6), 1.0, 5.0)

    for r in rows:
        spec = json.loads(r["spec_json"] or "{}")
        mk = maker_of(r["title"])
        ask = r["ask_cents"] or 0
        # ---- Axis 1: value for ask ----
        # hammer-beats-estimate or a present (non-zero) ask that is not absurdly
        # above source median => strong value; empty/no ask => neutral
        ratio = spec.get("hammer_to_est")
        if ratio is not None:
            v = clamp((ratio - 0.4) * (5.0 / 0.8), 1.0, 5.0)  # 0.6->1, 1.0->3.7, 1.2->5
        elif ask:
            # retail listing: value flips on condition/rarity metadata presence
            cond_bonus = 0.4 if (r["condition"] or spec.get("condition")) else 0.0
            v = clamp(3.0 + cond_bonus, 1.0, 5.0)
        else:
            v = 2.5
        # ---- Axis 2: rarity ----
        ryn = rarity_score(mk)
        if spec.get("full_set") or (r["condition"] or "").lower() in (
                "box & papers", "full set", "very good", "excellent"):
            ryn = min(5.0, ryn + 0.6)
        # ---- Axis 3: investment ----
        inv = invest_score(mk)
        if ratio is not None and ratio >= 1.2:
            inv = min(5.0, inv + 0.5)

        con.execute(
            "UPDATE items SET s_value=?, s_quality=?, s_desirability=? WHERE id=?",
            (v, ryn, inv, r["id"]))
    con.commit()

    # ---- rank per dept (ordering only; three scores always shown separate) ----
    depts = sorted(set(r["dept"] for r in rows))
    for d in depts:
        ids = [r["id"] for r in rows if r["dept"] == d]
        # rank by a documented composite: quality>value>desirability (tiebreak)
        scored = []
        for i in ids:
            rr = con.execute("SELECT s_value,s_quality,s_desirability FROM items "
                             "WHERE id=?", (i,)).fetchone()
            q, kval, des = rr["s_quality"], rr["s_value"], rr["s_desirability"]
            scored.append((i, kval, q, des))
        scored.sort(key=lambda x: (-x[1], -x[2], -x[3]))
        rank_order = [i for i, *_ in scored]
        # STYLE: the editorial intent is MEN'S-led with LADIES mixed in — never
        # one gender monopolizing the visible grid. Interleave the departure-
        # gender-agnostic score order so a genuine men+women mix shows at the top.
        if d == "style":
            def _gender(i):
                u = (con.execute("SELECT url FROM items WHERE id=?", (i,))
                     .fetchone()["url"] or "")
                if "/men/" in u or "grailed.com" in u or "vestiairecollective.com" in u:
                    return "m"
                return "w"    # RealReal women + Sotheby's bags are ladies'
            men = [i for i in rank_order if _gender(i) == "m"]
            wom = [i for i in rank_order if _gender(i) == "w"]
            mixed = []
            mi = wi = 0
            while mi < len(men) or wi < len(wom):
                if mi < len(men):                 # men lead the interleave
                    mixed.append(men[mi]); mi += 1
                if wi < len(wom):
                    mixed.append(wom[wi]); wi += 1
            rank_order = mixed
        for rank, i in enumerate(rank_order, 1):
            con.execute("UPDATE items SET rank=? WHERE id=?", (rank, i))
    con.commit()

    # ---- summary ----
    print("scored", len(rows), "items")
    for d in depts:
        cnt = con.execute("SELECT COUNT(*) c FROM items WHERE dept=?", (d,)).fetchone()["c"]
        avg = con.execute("SELECT AVG(s_quality) a, AVG(s_desirability) b, "
                          "AVG(s_value) c FROM items WHERE dept=?",
                          (d,)).fetchone()
        print(f"  {d:8} n={cnt:4} | rarity avg {avg['a']:.1f} | invest avg "
              f"{avg['b']:.1f} | value avg {avg['c']:.1f}")

if __name__ == "__main__":
    main()
