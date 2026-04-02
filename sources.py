## All websites the screener will visit.
# method: "firecrawl" = needs JavaScript rendering

SUBCATEGORIES = [
    "HVAC", "plumbing", "electrical contractor",
    "residential cleaning", "landscaping lawn care",
    "pest control", "moving storage", "appliance repair",
    "roofing", "pool service", "security systems",
    "distribution logistics",
    "commercial cleaning",
    "other",
]

TARGET_STATES = ["California", "Florida", "New Jersey", "New York"]

def get_sources():
    sources = []

    # ── BizEx ──────────────────────────────────────────────
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://www.bizex.net/business-for-sale/summary/46?keywords={s}&price_low=1000000&price_high=2000000",
            "source": "BizEx",
            "method": "firecrawl",
        })

    # ── DealStream ─────────────────────────────────────────
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://dealstream.com/businesses-for-sale?q={s}",
            "source": "DealStream",
            "method": "firecrawl",
        })

    # ── BizQuest ───────────────────────────────────────────
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://www.bizquest.com/businesses-for-sale/?q={s}&price_from=1000000&price_to=2000000",
            "source": "BizQuest",
            "method": "firecrawl",
        })

    # ── BusinessBroker.net — search by state + keyword ────
    # Confirmed publicly accessible with real listing data
  
    # ── Murphy Business ────────────────────────────────────
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://murphybusiness.com/business-brokerage/view-our-listings/?s={s.replace(' ', '+')}",
            "source": "Murphy Business",
            "method": "firecrawl",
        })

    # ── Sunbelt Network — by state ─────────────────────────
    for state in ["california", "florida", "new-jersey", "new-york"]:
        sources.append({
            "url": f"https://www.sunbeltnetwork.com/state/{state}/",
            "source": "Sunbelt",
            "method": "firecrawl",
         })   
        
    # ── Transworld ─────────────────────────────────────────
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://www.tworld.com/listings/?search={s.replace(' ', '+')}&min_price=1000000&max_price=2000000",
            "source": "Transworld",
            "method": "firecrawl",
        })
    # ── Synergy Business Brokers ───────────────────────────
    # Scrape by industry category pages, not the main listing page
    # (main page is FacetWP filtered, category pages load cleanly)
    for industry_url in [
        "https://synergybb.com/industries/service-businesses-for-sale/",
        "https://synergybb.com/industries/distributors-for-sale/",
        "https://synergybb.com/industries/construction-companies-for-sale/",
        "https://synergybb.com/businesses-for-sale/based-on-location/new-york/",
        "https://synergybb.com/businesses-for-sale/based-on-location/new-jersey/",
        "https://synergybb.com/businesses-for-sale/based-on-location/california/",
        "https://synergybb.com/businesses-for-sale/based-on-location/florida/",
    ]:
        sources.append({
            "url": industry_url,
            "source": "Synergy",
            "method": "firecrawl",
        })

    # ── HedgeStone Business Advisors ──────────────────────
    # Listings load publicly with asking price and cashflow
    sources.append({
        "url": "https://www.hedgestone.com/businesses-for-sale/",
        "source": "HedgeStone",
        "method": "firecrawl",
    })
    for industry_url in [
        "https://www.hedgestone.com/service-businesses/",
        "https://www.hedgestone.com/wholesale-businesses/",
    ]:
        sources.append({
            "url": industry_url,
            "source": "HedgeStone",
            "method": "firecrawl",
        })

    # ── Benjamin Ross Group ────────────────────────────────
    # HubSpot-powered, worth trying — Firecrawl handles JS
    sources.append({
        "url": "https://listings.benjaminrossgroup.com/",
        "source": "Benjamin Ross Group",
        "method": "firecrawl",
    })
        
    return sources
