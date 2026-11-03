# ME live-listing API hydration — PARKED SPEC (2026-11-01)

## Status
PARKED. Good idea, blocked by platform tooling, not by concept. Resume when live
access is easy or a token is on hand. Do NOT fabricate tokens/keys to force it.

## The confirmed insight (validated, not theory)
The walls are on the HTML documents; the JSON/GraphQL backends are open and alive:
- Sotheby's: `https://clientapi.prod.sothelabs.com/graphql` — responds to a bare POST
  (GraphQL engine processing; `introspection_enabled: false`). Works via curl_cffi
  Chrome-impersonation.
- Artsy: `https://metaphysics-production.artsy.net/v2` — GraphQL engine alive (returns
  real schema errors to any query). Public API v2 needs `X-Xapp-Token` (401 without).
- Boats Group (YachtWorld/Boat Trader/boats.com): licensed REST feed `api.boats.com`
  — PAID. Do NOT touch without explicit go (no-paid-spend lock).
- Christie's: no documented API; results archive is an XHR JSON backend — reverse from
  devtools once, stable for months.

## General technique (for resume)
1. In a real browser, open devtools > Network > Fetch/XHR.
2. Scroll the results grid to fire the listing XHR.
3. Grab the endpoint + required headers (auth/xapp token are public search-only creds).
4. Replay with curl_cffi impersonating Chrome. Search-only/algolia keys are designed public
   (no wall, generous rate limits). Default no: don't crack paywalls or CAPTCHAs.

## What's already staged (works)
- `~/.hermes/venv... no —` at `/Users/nolanfarrell/sites/mostexpensivest/.venv-me`
  (curl_cffi installed).
- `media/live_listings.json` — source-of-truth manifest (departments + heroes).
- Daily manager `~/.hermes/scripts/me_llist_manager.sh` — re-verifies all URLs (curl -L,
  LIVE/WALL/DEAD), silent when clean. Cron `me-listing-manager` daily 10am.
- Weekly researcher `~/.hermes/scripts/me_listing_researcher.py` — probes per-category
  candidates, HTTP-verifies, separates LIVE from WALL from DEAD. Cron `me-listing-research`
  Wed noon. Output: `media/listing_candidates.json`.
- 31 LIVE listings folded in, 0 DEAD. Heroes data-driven.
- House-grade card metadata line is BUILT and live (2026-11-03): Time cards render
  only-populated fields (case material, case size, movement, complications) from the
  MostExpensiveWatches feed; `condition` and `box_papers` slots sit in the frame and
  fill in automatically once the feed carries them. Shared loader
  (`js/market-loader.js`) has the same metadata frame, so other departments adopt the
  pattern as their feeds gain item data. Site pushed to origin/main (clean).

## Card-frame priority (field survey, 2026-11-03)
Market leaders (1stDibs, LiveAuctioneers, Phillips, Fashionphile, RealReal, Grailed,
Watchfinder, et al.) all lead market-first: rail above grid, borderless cards, image-top,
small-caps house line, bold price — no editorial-hero pattern. The condition, certificate,
and provenance fields are what make a frame read as a house rather than a classifieds page;
they are the true prize for Time, The Field, and Art, and they are the fields ME's feed
still does not carry. When tools reset: 1stDibs and Grailed are researched first, then the
condition-field sources.

## WHAT TO DO TO RESUME
1. Park continues to guard the site daily (no change needed).
2. When a real xapp/API token is available, OR a documented-generic query shape is found,
   slot it into a new `~/.hermes/scripts/me_api_researcher.py` (curl_cffi) and wire the
   feed into `live_listings.json` + department pages.
3. First target on resume: Sotheby's GraphQL (already answers bare POSTs) — find one
   working `lots`/`sale` query shape; second: Artsy once a live X-Xapp-Token is on hand.

## Guardrails
- Never fabricate a token or invent listing data. HTTP-verify everything.
- No paid API spend (Boats Group, others) without explicit go.
- No CAPTCHA/Cloudflare bypass.
