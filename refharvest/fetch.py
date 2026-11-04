import os, time
import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}
BLOCK = {401, 403, 429, 503}


class Blocked(Exception):
    pass


def _proxy_prefix():
    p = os.environ.get("READER_PROXY")
    return (p.rstrip("/") + "/") if p else None


def wayback(url, timeout=30):
    """Recover a blocked page from the Wayback Machine. Returns (body, stamp).
    A snapshot is context, not live data — callers must treat prices/availability
    on it as as-of-the-snapshot-date, never current."""
    cdx = ("http://web.archive.org/cdx/search/cdx?url=" + url +
           "&output=json&limit=1&filter=statuscode:200&collapse=digest")
    hits = requests.get(cdx, timeout=timeout).json()
    if len(hits) < 2:
        raise Blocked("no snapshot")
    stamp, orig = hits[1][1], hits[1][2]
    body = requests.get(f"https://web.archive.org/web/{stamp}id_/{orig}",
                        headers=HEADERS, timeout=timeout).text
    return body, stamp


# provenance of the most recent get(): {"source":"live"} or
# {"source":"wayback","stamp":"20261103..."}. Reads it after a recover=True fetch.
LAST = {"source": "live", "stamp": None}


def _provider():
    return os.environ.get("FETCH_PROVIDER", "direct")


def via_provider(url, timeout=45):
    """Route a blocked page through a configured fetch provider.
    Keyless today: jina (low volume, no key) and wayback. The keyed providers
    (scraperapi / scrapingbee / firecrawl) fail soft unless their env key is set —
    never spend without an explicit go (no-paid-spend lock)."""
    p = _provider()
    if p == "jina":
        h = dict(HEADERS)
        if os.environ.get("JINA_KEY"):
            h["Authorization"] = "Bearer " + os.environ["JINA_KEY"]
        return requests.get("https://r.jina.ai/" + url, headers=h, timeout=timeout).text
    if p == "scraperapi":
        if not os.environ.get("SCRAPERAPI_KEY"):
            raise Blocked("scraperapi: no key set")
        return requests.get("http://api.scraperapi.com",
                            params={"api_key": os.environ["SCRAPERAPI_KEY"],
                                    "url": url}, timeout=timeout).text
    if p == "scrapingbee":
        if not os.environ.get("SCRAPINGBEE_KEY"):
            raise Blocked("scrapingbee: no key set")
        return requests.get("https://app.scrapingbee.com/api/v1/",
                            params={"api_key": os.environ["SCRAPINGBEE_KEY"],
                                    "url": url}, timeout=timeout).text
    if p == "firecrawl":
        if not os.environ.get("FIRECRAWL_KEY"):
            raise Blocked("firecrawl: no key set")
        r = requests.post("https://api.firecrawl.dev/v1/scrape",
                          headers={"Authorization": "Bearer " +
                                   os.environ["FIRECRAWL_KEY"]},
                          json={"url": url, "formats": ["html"]},
                          timeout=timeout)
        return r.json()["data"]["html"]
    if p == "wayback":
        body, _stamp = wayback(url, timeout)
        return body
    raise Blocked("no provider configured")


def get(url, render=False, tries=3, timeout=40, proxy=None, recover=False):
    """Fetch a page (optionally rendered). Returns text — same shape as before,
    so existing callers are unchanged.

    Order: when a FETCH_PROVIDER is configured (jina / wayback / keyed proxies),
    try it FIRST — a server-side render clears bot walls and returns real HTML,
    so it outranks a direct request. A short (<2000 chars) provider body is a
    stub and is rejected. Direct route next, wayback as the final net on a hard
    block (when recover=True). Provenance of the last fetch is in module LAST."""
    proxy = proxy if proxy is not None else _proxy_prefix()
    last = None
    p = _provider()
    for n in range(tries):
        try:
            if p != "direct":
                try:
                    html = via_provider(url, timeout)
                    if html and len(html) > 2000:
                        LAST["source"] = p
                        LAST["stamp"] = None
                        return html
                except Exception as e:                # noqa: BLE001
                    last = e
            if render:
                text = _render(url, timeout)
            else:
                target = (proxy + url) if proxy else url
                r = requests.get(target, headers=HEADERS, timeout=timeout)
                if r.status_code in BLOCK:
                    raise Blocked(f"HTTP {r.status_code}")
                r.raise_for_status()
                text = r.text
            LAST["source"] = "live"
            LAST["stamp"] = None
            return text
        except Blocked:
            if recover:
                if p != "direct":
                    try:
                        body = via_provider(url, timeout)
                        if body and len(body) > 2000:
                            LAST["source"] = p
                            LAST["stamp"] = None
                            return body
                    except Blocked:
                        pass
                try:
                    body, stamp = wayback(url, timeout)
                    LAST["source"] = "wayback"
                    LAST["stamp"] = stamp
                    return body
                except Blocked:
                    raise
            raise
        except Exception as e:                       # noqa: BLE001
            last = e
            time.sleep(2 ** n)
    raise last


def _render(url, timeout):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        kw = {"args": ["--disable-blink-features=AutomationControlled"]}
        try:
            browser = pw.chromium.launch(channel="chrome", **kw)
        except Exception:                            # noqa: BLE001
            browser = pw.chromium.launch(**kw)
        ctx = browser.new_context(user_agent=UA, locale="en-GB",
                                 viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        page.wait_for_timeout(3500)
        for _ in range(3):
            page.mouse.wheel(0, 2400)
            page.wait_for_timeout(900)
        html = page.content()
        browser.close()
        return html


def head_ok(url, timeout=20):
    """Status probe that tolerates HEAD being unsupported."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=timeout,
                          allow_redirects=True)
        if r.status_code >= 400:
            r = requests.get(url, headers=HEADERS, timeout=timeout,
                             allow_redirects=True, stream=True)
        return r.status_code
    except Exception:                                # noqa: BLE001
        return 0