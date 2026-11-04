#!/usr/bin/env python3
"""ME feed refresh — orchestrate the full data pipeline on this machine.

Runs, in order, all of the live-holding pullers + the scorer + the feed export,
so one command refreshes the whole site feed. Idempotent (each puller upserts on
unique URL). Failures are collected and reported, not fatal — a source that
rate-limits or changes shape is logged and the run continues, so one bad source
never blanks the feed.

        python3 refresh.py

Exit code 0 if all steps ran (even if some sources failed); steps that failed
are printed. The link-health cron calls this so the feed stays current while
the Mac is up. Fetch is via FETCH_PROVIDER=jina for the keyless render route.
"""
import os, subprocess, sys, json

ROOT = "/Users/nolanfarrell/sites/mostexpensivest/refharvest"
PY = os.path.join(ROOT, ".venv", "bin", "python3")

# (script, label, needs_jina) — order matters: pullers first, then score/export.
STEPS = [
    ("holts_lots.py",      "Holt's auction lots (field)", False),
    ("sothebys_lots.py",   "Sotheby's handbags (style)", False),
    ("bat_lots.py",        "Bring a Trailer (road)", False),
    ("fraser_yachts.py",   "Fraser Yachts (sea)", False),
    ("realreal_items.py",  "The RealReal (style, via jina)", True),
    ("invaluable_art.py",  "Invaluable fine art (via jina)", True),
    ("jamesedition_estates.py", "JamesEdition estates (via jina)", True),
    ("score.py",           "score value/rarity/investment", False),
    ("export_feed.py",     "export out/feed.json", False),
]

def run():
    env = dict(os.environ)
    env["ROOT"] = ROOT
    failures = []
    for script, label, needs_jina in STEPS:
        path = os.path.join(ROOT, script)
        if not os.path.exists(path):
            failures.append(f"{label}: missing script {script}")
            continue
        print(f"[refreshing] {label} ...")
        step_env = dict(env)
        # keyless server-side render is only needed for the walled hosts
        step_env["FETCH_PROVIDER"] = "jina" if needs_jina else "direct"
        try:
            p = subprocess.run([PY, path], cwd=ROOT, env=step_env,
                               capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            failures.append(f"{label}: timed out")
            continue
        if p.returncode != 0:
            tail = (p.stderr or p.stdout or "").strip().splitlines()
            msg = (tail[-1][:200] if tail else f"exit {p.returncode}")
            failures.append(f"{label}: {msg}")
        else:
            # surface the script's own summary line (e.g. '+421 lots')
            out = (p.stdout or "").strip().splitlines()
            if out:
                print("   ", out[-1])
    if failures:
        print("\n=== refreshed with N notes ===")
        for f in failures:
            print("  WARN", f)
    else:
        print("\nfeed refreshed clean")
    return 0

if __name__ == "__main__":
    sys.exit(run())
