# All websites the screener will visit.
# method: "firecrawl" = needs JavaScript rendering
#         "http" = plain page, loads fast

SUBCATEGORIES = [
    "HVAC", "plumbing", "electrical contractor",
    "residential cleaning", "landscaping lawn care",
    "pest control", "moving storage", "appliance repair",
    "roofing", "pool service", "security systems",
    "distribution logistics",
]

def get_sources():
    sources = []

    # BizEx — works great with Firecrawl
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://www.bizex.net/business-for-sale/summary/46?keywords={s}&price_low=1000000&price_high=2000000",
            "source": "BizEx",
            "method": "firecrawl",
        })

    # DealStream
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://dealstream.com/businesses-for-sale?q={s}",
            "source": "DealStream",
            "method": "firecrawl",
        })

    # BizQuest
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://www.bizquest.com/businesses-for-sale/?q={s}&price_from=1000000&price_to=2000000",
            "source": "BizQuest",
            "method": "firecrawl",
        })

    # Transworld Business Advisors
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://www.tworld.com/listings/?search={s}&min_price=1000000&max_price=2000000",
            "source": "Transworld",
            "method": "firecrawl",
        })

    # BusinessesForSale.com
    for s in SUBCATEGORIES:
        sources.append({
            "url": f"https://www.businessesforsale.com/search?q={s}&price_from=1000000&price_to=2000000&country=US",
            "source": "BusinessesForSale",
            "method": "firecrawl",
        })

    return sources
