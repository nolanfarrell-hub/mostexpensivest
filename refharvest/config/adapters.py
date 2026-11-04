"""Per-source behaviour. Fallback templates use spec fields, so every link
degrades to a faceted search instead of dying."""

ADAPTERS = {
    "chrono24.com": {
        "fallback": "@url:`https://www.chrono24.com/search/index.htm?query=`{ref}&dosearch=true",
        "spec": ["ref", "brand"],
    },
    "yachtworld.com": {
        "fallback": "@url:`https://www.yachtworld.com/boats-for-sale/make-`{make}/",
        "spec": ["make", "length"],
    },
    "yatco.com": {
        "fallback": "@url:`https://www.yatco.com/yachts-for-sale/`",
        "spec": ["brand"],
    },
    "fraseryachts.com": {
        "fallback": "@url:`https://www.fraseryachts.com/en/buy-a-yacht/`",
        "spec": [],
    },
    "bringatrailer.com": {
        "fallback": "@url:`https://bringatrailer.com/search/?q=`{q}",
        "spec": ["q"],
    },
    "collectingcars.com": {
        "fallback": "@url:`https://collectingcars.com/search?q=`{q}",
        "spec": ["q"],
    },
    "1stdibs.com": {
        "fallback": "@url:`https://www.1stdibs.com/buy/`{q}/",
        "spec": ["q"], "render": True,
    },
    "vestiairecollective.com": {
        "fallback": "@url:`https://us.vestiairecollective.com/search/?q=`{q}",
        "spec": ["q"],
    },
    "grailed.com": {
        "fallback": "@url:`https://www.grailed.com/shop?query=`{q}",
        "spec": ["q"],
    },
    "fashionphile.com": {
        "fallback": "@url:`https://www.fashionphile.com/shop?q=`{q}",
        "spec": ["q"],
    },
    "therealreal.com": {
        "fallback": "@url:`https://www.therealreal.com/shop?q=`{q}",
        "spec": ["q"],
    },
    "net-a-porter.com": {
        "fallback": "@url:`https://www.net-a-porter.com/en-us/search?q=`{q}",
        "spec": ["q"], "render": True,
    },
    "artsy.net": {
        "fallback": "@url:`https://www.artsy.net/search?q=`{q}",
        "spec": ["q"],
    },
    "liveauctioneers.com": {
        "fallback": "@url:`https://www.liveauctioneers.com/search/?query=`{q}",
        "spec": ["q"],
    },
    "holtsauctioneers.com": {
        "fallback": "@url:`https://www.holtsauctioneers.com/`",
        "spec": ["q"],
    },
    "sothebysrealty.com": {
        "fallback": "@url:`https://www.sothebysrealty.com/eng/sales/usa`",
        "spec": [],
    },
    "compass.com": {
        "fallback": "@url:`https://www.compass.com/homes-for-sale/`",
        "spec": [],
    },
    "whiskyauctioneer.com": {
        "fallback": "@url:`https://whiskyauctioneer.com/search?query=`{q}",
        "spec": ["q"],
    },
}

DEFAULT = {"fallback": None, "spec": [], "render": False}


def for_host(host):
    host = (host or "").lower().removeprefix("www.").removeprefix("us.")
    for k, v in ADAPTERS.items():
        if host.endswith(k):
            return {**DEFAULT, **v}
    return dict(DEFAULT)
