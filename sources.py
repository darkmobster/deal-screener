"""Public listing pages permitted for unattended DealOS monitoring.

Native alerts remain the preferred route for marketplaces that block or render
listing pages dynamically. The collector records a failure instead of bypassing
authentication, CAPTCHAs, paywalls, robots restrictions, or rate limits.
"""

SOURCES = [
    ("BizBuySell", "https://www.bizbuysell.com/"),
    ("BizQuest", "https://www.bizquest.com/"),
    ("Transworld", "https://www.tworld.com/listings/"),
    ("Embrace Benchmark", "https://embracebenchmark.com/"),
    ("Rejigg", "https://www.rejigg.com/for-sale/home-and-facility-services"),
    ("DealStream", "https://dealstream.com/businesses-for-sale"),
    ("BizEx", "https://www.bizex.net/business-for-sale/summary/46"),
    ("HedgeStone Business Advisors", "https://www.hedgestone.com/businesses-for-sale/"),
    ("BizMLS", "https://www.bizmls.com/businesses.htm"),
    ("LINK Business", "https://linkbusiness.com/businesses-for-sale/search?sortBy=LatestListing&page=1&searchByName=True&commissionSplit=AllListings"),
    ("First Choice Business Brokers", "https://fcbb.com/businesses-for-sale"),
    ("Moxie Brokerage Group", "https://www.moxiebrokeragegroup.com/"),
    ("Synergy Business Brokers", "https://synergybb.com/"),
    ("American Business Brokers", "https://www.americanbusinessbrokers.com/"),
    ("VR Business Sales", "https://www.vrbusinessbrokers.com/"),
    ("Endeavor Business Brokers", "https://www.endeavorbusinessbrokers.com/"),
    ("BusinessesForSale.com", "https://www.businessesforsale.com/"),
    ("Aria Business Advisors", "https://www.aria.net/listings"),
    ("Dealonomy", "https://dealonomy.com/"),
    ("New Jersey Business Brokers", "https://njbrokerplus.com/listings-over-one-million/"),
    ("The NYBB Group", "https://thenybbgroup.com/businesses-for-sale/"),
    ("Inbar Group", "https://inbargroup.com/businesses-for-sale/"),
    ("Morgan & Westfield", "https://morganandwestfield.com/buy/businesses-for-sale/"),
    ("Franchise Brokers Association Resales", "https://resales.franchiseba.com/resale-search"),
    ("Murphy Business", "https://murphybusiness.com/business-brokerage/view-our-listings"),
    ("Murray & Associates", "https://murraybizbuy.com/businesses-for-sale/"),
]


def get_sources():
    return [
        {"source": source, "url": url, "method": "firecrawl"}
        for source, url in SOURCES
    ]
