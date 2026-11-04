# Reference + live-link harvest

## Install
    pip install -r requirements.txt
    # only for JS-rendered sources:
    pip install playwright && playwright install chrome

## Run order
1. Structure harvest (reference, once per source)
    python harvest.py --mode structure --targets config/targets.json \
        --out out --only wall
2. Item harvest (candidates, repeatable)
    python harvest.py --mode items --targets config/targets.json \
        --delay 4 --limit 40
3. Cache images
    python images.py --limit 40
4. Score by hand in the DB (s_value, s_quality, s_desirability, rank)
5. Export the site feed
    python harvest.py --mode items --targets config/targets.json \
        --limit 0 --export out/feed.json

## Ongoing (cron)
    */180 * * * * cd /srv/refharvest && python links.py --limit 60
    # dead or sold items auto-switch to their fallback search URL

## Blocked hosts
Set READER_PROXY=https://r.jina.ai/ and skip --render for those hosts.
Proxy returns rails but loses class names; browser returns anatomy. Use both.

## Notes
- Fallback templates in config/adapters.py are the anti-rot layer. Every item
  must have one before it can be ranked.
- Selectors are heuristic. When a source extracts badly, add explicit
  selectors to its adapter rather than loosening the generic extractor.
- `state` values: live | sold | dead | blocked. Only live items serve their
  direct URL; the rest serve the fallback.