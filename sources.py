## All websites the screener will visit.
# method: "firecrawl" = needs JavaScript rendering
#
# Filter strategy:
#   - Large platforms (BizQuest, Transworld, DealStream): URL params for
#     subcategory + price range baked into every request.
#   - Sunbelt / Morgan & Westfield: state-level URL params.
#   - Regional broker sites: listing pages are already state-scoped; no URL
#     filter params available — buy-box screening happens at the AI stage.

SUBCATEGORIES = [
    "home inspection",
    "residential cleaning",
    "commercial cleaning",
    "pest control",
    "moving storage",
    "appliance repair",
    "roofing",
    "pool service",
    "security systems",
    "distribution logistics",
    "gym",
    "fitness center",
    "bathhouse",
    "sauna",
]

TARGET_STATES = ["California", "Florida", "New Jersey", "New York", "Massachusetts"]


def get_sources():
    sources = []

    # ── DealStream ─────────────────────────────────────────────────────────────
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://dealstream.com/businesses-for-sale?q={s}",
            "source": "DealStream",
            "method": "firecrawl",
        })

    # ── BizQuest ───────────────────────────────────────────────────────────────
    # Filters: subcategory keyword + price $1M–$2.5M
    for s in SUBCATEGORIES:
        sources.append({
            "url": (
                f"https://www.bizquest.com/businesses-for-sale/"
                f"?q={s}&price_from=1000000&price_to=2500000"
            ),
            "source": "BizQuest",
            "method": "firecrawl",
        })

    # ── Sunbelt Network — by state ─────────────────────────────────────────────
    for state in ["california", "florida", "new-jersey", "new-york"]:
        sources.append({
            "url": f"https://www.sunbeltnetwork.com/state/{state}/",
            "source": "Sunbelt",
            "method": "firecrawl",
        })

    # ── Transworld ────────────────────────────────────────────────────────────
    # Filters: subcategory keyword + price $1M–$2.5M
    for s in SUBCATEGORIES:
        sources.append({
            "url": (
                f"https://www.tworld.com/listings/"
                f"?search={s.replace(' ', '+')}&min_price=1000000&max_price=2500000"
            ),
            "source": "Transworld",
            "method": "firecrawl",
        })

    # ── Morgan & Westfield — national, filtered by target state ───────────────
    for state in ["california", "florida", "new-jersey", "new-york"]:
        sources.append({
            "url": f"https://morganandwestfield.com/buy/businesses-for-sale/?state={state}",
            "source": "MorganAndWestfield",
            "method": "firecrawl",
        })

    # ── New York brokers ───────────────────────────────────────────────────────
    for url, source in [
        ("https://thenybbgroup.com/businesses-for-sale/",             "TheNYBBGroup"),
        ("https://inbargroup.com/businesses-for-sale/",               "InbarGroup"),
        ("https://vestedbb.com/businesses-for-sale/",                 "VestedBB"),
        ("https://businessesforsaleinnewyorkcity.com/businesses-for-sale/", "FCBBNewYorkCity"),
    ]:
        sources.append({"url": url, "source": source, "method": "firecrawl"})

    # ── New Jersey brokers ────────────────────────────────────────────────────
    # njbrokerplus + acquisitionexperts are pre-filtered to $1M+ listings
    for url, source in [
        ("https://inbargroup.com/new-jersey-business-brokers/",       "InbarGroup-NJ"),
        ("https://njbrokerplus.com/listings-over-one-million/",       "NJBrokerPlus"),
        ("https://murraybizbuy.com",                                   "MurrayBizBuy"),
        ("https://atlanticbusinessbroker.com/our-business-for-sale-listings", "AtlanticBizBroker"),
    ]:
        sources.append({"url": url, "source": source, "method": "firecrawl"})

    # ── Florida brokers ───────────────────────────────────────────────────────
    # acquisitionexperts pre-filtered to $1M+ listings
    for url, source in [
        ("https://www.floridama.com/listings/",                        "FloridaMA"),
        ("https://kmfbusinessadvisors.dealrelations.com/listings",     "KMFBusinessAdvisors"),
        ("https://acquisitionexperts.net/million-dollar-plus-business-listings/", "AcquisitionExperts"),
    ]:
        sources.append({"url": url, "source": source, "method": "firecrawl"})

    # ── California brokers ────────────────────────────────────────────────────
    for url, source in [
        ("https://californiabusinessbrokers.com/for-sale-2/",          "CalBizBrokers"),
        ("https://thebusinessbrokerslosangeles.com",                   "BizBrokersLA"),
        ("https://zoombusinessbrokers.com",                            "ZoomBizBrokers"),
        ("https://exitstrategiesgroup.com",                            "ExitStrategiesGroup"),
    ]:
        sources.append({"url": url, "source": source, "method": "firecrawl"})

    # ── Massachusetts brokers (multi-state — AI screening enforces state filter)
    for url, source in [
        ("https://inbargroup.com/boston-business-broker/",             "InbarGroup-Boston"),
        ("https://boston.fcbb.com/businesses-for-sale",                "FCBBBoston"),
        ("https://baystatebusinessbrokers.com",                        "BayStateBizBrokers"),
        ("https://goodmanonline.com",                                  "GoodmanAndCompany"),
        ("https://georgeandco.com",                                    "GeorgeAndCompany"),
    ]:
        sources.append({"url": url, "source": source, "method": "firecrawl"})

    return sources
