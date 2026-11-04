import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PRICE = re.compile(r"(?P<cur>[$£€]|CHF\s?|USD\s?|GBP\s?)\s?"
                   r"(?P<num>\d[\d.,]*)", re.I)
COND = re.compile(r"\b(new|never worn|gently used|used|very worn|excellent|"
                  r"very good|good|fair|pristine|giftable|no reserve|"
                  r"project|restored|original)\b", re.I)
SKIP = {"script", "style", "noscript", "svg"}


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def cents(match):
    num = match.group("num").replace(",", "")
    try:
        return int(float(num) * 100)
    except ValueError:
        return None


def modules(soup, minimum=8):
    sig = {}
    for el in soup.find_all(True):
        if el.name in SKIP or el.find("img") is None:
            continue
        par = el.parent
        if par is None or par.name in SKIP:
            continue
        key = (el.name, tuple(el.get("class", []))[:2],
               par.name, tuple(par.get("class", []))[:2])
        sig.setdefault(key, []).append(el)
    groups = [(k, v) for k, v in sig.items() if len(v) >= minimum]
    if not groups:
        return []
    groups.sort(key=lambda kv: -len(kv[1]))
    return groups[0][1]


def spec_fields(text, keys):
    """Best-effort spec capture for fallback templating."""
    out = {}
    if not keys:
        return out
    if "ref" in keys:
        m = re.search(r"\b(?:ref(?:erence)?\.?\s*:?\s*)([A-Z0-9][A-Z0-9\-/]{2,})",
                      text, re.I)
        if m:
            out["ref"] = m.group(1)
    if "q" in keys:
        out["q"] = clean(text)[:60]
    for k in ("brand", "make", "length"):
        if k in keys:
            out[k] = clean(text.split(" ")[0])[:30]
    return out


def items_from(soup, base_url, adapter, dept, source):
    recs = []
    for mod in modules(soup):
        link = mod.find("a", href=True)
        img = mod.find("img")
        text = clean(mod.get_text())
        if len(text) < 8:
            continue
        pm = PRICE.search(text)
        cm = COND.search(text)
        rec = {
            "dept": dept, "source": source,
            "url": urljoin(base_url, link["href"]) if link else base_url,
            "title": text[:160],
            "ask_cents": cents(pm) if pm else None,
            "currency": (pm.group("cur").strip().upper() if pm else None),
            "condition": cm.group(1).title() if cm else None,
            "spec": spec_fields(text, adapter.get("spec") or []),
        }
        if img is not None:
            src = img.get("src") or img.get("data-src")
            if src:
                rec["image_src"] = urljoin(base_url, src)
        tpl = adapter.get("fallback")
        if tpl:
            try:
                rec["fallback_url"] = tpl.format(**{**{"q": rec["title"][:40]},
                                                    **rec["spec"]})
            except KeyError:
                rec["fallback_url"] = tpl.split("{")[0]
        recs.append(rec)
    return recs


def structure(soup, url):
    """Reference-mode report: anatomy, facets, type scale, columns."""
    from collections import Counter
    facets, links = [], []
    for el in soup.find_all(True):
        blob = " ".join(filter(None, [el.get("id", ""), el.get("aria-label", ""),
                                      " ".join(el.get("class", []))]))
        if not re.search(r"filter|refine|facet|sort|rail", blob, re.I):
            continue
        for lab in el.find_all(["dt", "legend", "h2", "h3", "h4", "label",
                                "button", "summary"]):
            t = clean(lab.get_text())
            if 2 <= len(t) <= 40:
                facets.append(t)
        for a in el.find_all("a", href=True):
            if re.search(r"(creator|designer|period|condition|brand|make|"
                         r"medium|size|region)=", a["href"], re.I):
                links.append(a["href"][:140])
    mods = modules(soup, 4)
    anatomy = []
    if mods:
        for node in mods[0].find_all(True):
            if node.name in SKIP:
                continue
            step = {"tag": node.name}
            txt = clean(node.get_text())[:70]
            if txt and not node.find(True):
                step["text"] = txt
            if PRICE.search(txt):
                step["price"] = True
            anatomy.append(step)
    sizes = Counter()
    for st in soup.find_all("style"):
        for m in re.finditer(r"font-size:\s*([\d.]+)(px|rem)", st.get_text()):
            sizes[f"{m.group(1)}{m.group(2)}"] += 1
    return {
        "url": url,
        "title": clean(soup.title.get_text()) if soup.title else "",
        "card_repeats": len(mods),
        "anatomy": anatomy[:40],
        "facets": list(dict.fromkeys(facets))[:200],
        "facet_links": list(dict.fromkeys(links))[:100],
        "type_sizes": sizes.most_common(12),
    }


def soup_of(html):
    return BeautifulSoup(html, "lxml")