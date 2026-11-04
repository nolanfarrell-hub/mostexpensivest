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


def get(url, render=False, tries=3, timeout=40, proxy=None):
    proxy = proxy if proxy is not None else _proxy_prefix()
    last = None
    for n in range(tries):
        try:
            if render:
                return _render(url, timeout)
            target = (proxy + url) if proxy else url
            r = requests.get(target, headers=HEADERS, timeout=timeout)
            if r.status_code in BLOCK:
                raise Blocked(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.text
        except Blocked:
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