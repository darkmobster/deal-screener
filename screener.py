import os, json, time, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import requests
from supabase import create_client
from anthropic import Anthropic
from sources import get_sources
from urllib.parse import quote_plus

# ── Load credentials from environment ──────────────────
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]
FIRECRAWL_KEY   = os.environ["FIRECRAWL_API_KEY"]
SUPABASE_URL    = os.environ["SUPABASE_URL"]
SUPABASE_KEY    = os.environ["SUPABASE_KEY"]
GMAIL_USER      = os.environ["GMAIL_USER"]
GMAIL_PASSWORD  = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)

# ── Load buy-box from CLAUDE.md ─────────────────────────
BUY_BOX = Path("CLAUDE.md").read_text()

# ── Clients ─────────────────────────────────────────────
claude   = Anthropic(api_key=ANTHROPIC_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def scrape(source):
    """Fetch a page using Firecrawl and return markdown text."""
    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_KEY}"},
            json={
                "url": source["url"],
                "formats": ["markdown"],
                "onlyMainContent": True,
                "timeout": 30000,
            },
            timeout=40,
        )
        data = resp.json()
        text = data.get("data", {}).get("markdown", "")
        return text[:4000] if len(text) > 100 else ""
    except Exception as e:
        print(f"Scrape error {source['url']}: {e}")
        return ""

def score_listing(text, source_url):
    """Send listing text to Claude and get a score back."""
    try:
        msg = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=BUY_BOX,
            messages=[{"role": "user", "content": f"Score this listing:\n\n{text}"}],
        )
        raw = msg.content[0].text
        match = __import__("re").search(r"\{[\s\S]*\}", raw)
        if match:
            result = json.loads(match.group())
            result["listing_url"] = result.get("listing_url") or source_url
            return result
    except Exception as e:
        print(f"Score error: {e}")
    return None

def save_to_supabase(deal):
    """Save a deal to the database, skipping duplicates."""
    try:
        supabase.table("listings").upsert({
            "title":        deal.get("title", "Unknown"),
            "location":     deal.get("location", ""),
            "state":        deal.get("state", ""),
            "asking_price": deal.get("asking_price", 0),
            "sde":          deal.get("sde", 0),
            "match_score":  deal.get("match_score", 0),
            "green_flags":  json.dumps(deal.get("green_flags", [])),
            "red_flags":    json.dumps(deal.get("red_flags", [])),
            "listing_url":  deal.get("listing_url", ""),
            "is_new":       True,
        }, on_conflict="listing_url").execute()
    except Exception as e:
        print(f"DB error: {e}")

def send_email(deals):
    """Send the digest email."""
    from datetime import date
    today = date.today().strftime("%B %d, %Y")
    subject = f"Deal Screener: {len(deals)} new matches today" if deals else "Deal Screener: No matches today"

    cards = ""
    for d in deals:
        price  = f"${d.get('asking_price',0):,}"
        sde    = f"${d.get('sde',0):,}"
        score  = d.get("match_score", 0)
        flags  = ", ".join(d.get("green_flags", [])[:3])
        url    = d.get("listing_url", "#")
        cards += f"""
        <div style="border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <h3 style="font-size:16px;margin:0 0 4px;">{d.get('title','')}</h3>
              <p style="color:#64748b;font-size:13px;margin:0;">{d.get('location','')}</p>
            </div>
            <span style="background:#1e40af;color:white;padding:6px 14px;border-radius:20px;font-size:15px;font-weight:600;">{score}%</span>
          </div>
          <div style="display:flex;gap:24px;margin:14px 0;font-size:14px;">
            <span><b>Price:</b> {price}</span>
            <span><b>SDE:</b> {sde}</span>
          </div>
          <p style="color:#059669;font-size:13px;margin:0 0 12px;">✓ {flags}</p>
          <a href="{url}" style="background:#2563eb;color:white;padding:8px 20px;border-radius:8px;text-decoration:none;font-size:14px;">View Listing →</a>
        </div>"""

    body = f"""<html><body style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:32px 16px;">
    <h1 style="font-size:24px;">{len(deals)} new matches · {today}</h1>
    <p style="color:#64748b;">All scored ≥70/100 against your buy-box</p>
    {cards if cards else "<p>No listings matched today's criteria.</p>"}
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
    print(f"Email sent: {subject}")

def main():
    sources = get_sources()
    print(f"Checking {len(sources)} sources...")
    matches = []
    seen_titles = set()

    for i, source in enumerate(sources):
        print(f"[{i+1}/{len(sources)}] {source['source']} — {source['url'][:60]}")
        text = scrape(source)
        if not text:
            continue

        deal = score_listing(text, source["url"])
        if not deal:
            continue

        score = deal.get("match_score", 0)
        title = deal.get("title", "").lower().strip()

        if score >= 70 and title not in seen_titles and title:
            seen_titles.add(title)
            matches.append(deal)
            save_to_supabase(deal)
            print(f"  ✓ MATCH: {deal.get('title')} — score {score}")
        else:
            print(f"  — No match (score: {score})")

        time.sleep(5)  # be polite to Firecrawl's free tier

    send_email(matches)
    print(f"Done. {len(matches)} matches found.")

if __name__ == "__main__":
    main()
