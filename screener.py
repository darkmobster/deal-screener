import os, json, time, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import requests
from dotenv import load_dotenv
from anthropic import Anthropic
from sources import get_sources
from urllib.parse import quote_plus

load_dotenv()

# ── Load credentials from environment ──────────────────
ANTHROPIC_KEY       = os.environ["ANTHROPIC_API_KEY"]
FIRECRAWL_KEY       = os.environ["FIRECRAWL_API_KEY"]
AIRTABLE_API_KEY    = os.environ["AIRTABLE_API_KEY"]
AIRTABLE_BASE_ID    = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE_ID   = os.environ["AIRTABLE_DEALS_TABLE_ID"]
GMAIL_USER          = os.environ["GMAIL_USER"]
GMAIL_PASSWORD      = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL     = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)

# ── Load buy-box from CLAUDE.md ─────────────────────────
BUY_BOX = Path("CLAUDE.md").read_text()

# ── Clients ─────────────────────────────────────────────
claude = Anthropic(api_key=ANTHROPIC_KEY)

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
    import re
    try:
        msg = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=BUY_BOX,
            messages=[{"role": "user", "content": f"This page may contain multiple listings. Find the single best matching listing and score only that one.\n\n{text}"}],
        )
        raw = msg.content[0].text
        # Extract only the first valid JSON object
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", raw, re.DOTALL)
        if not match:
            match = re.search(r"\{[\s\S]*?\}(?=\s*$|\s*\{)", raw)
        if match:
            result = json.loads(match.group())
            result["listing_url"] = result.get("listing_url") or source_url
            return result
    except Exception as e:
        print(f"Score error: {e}")
    return None

def save_to_airtable(deal):
    """Save a deal to Airtable as a new record."""
    from datetime import date
    green_flags = deal.get("green_flags", [])
    red_flags   = deal.get("red_flags", []) + deal.get("mismatches", [])
    try:
        resp = requests.post(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}",
            headers={
                "Authorization": f"Bearer {AIRTABLE_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={"fields": {
                "Deal Name":     deal.get("title", "Unknown"),
                "Asking Price":  deal.get("asking_price", 0),
                "SDE":           deal.get("sde", 0),
                "Industry":      deal.get("industry", ""),
                "State":         deal.get("state", ""),
                "Broker Name":   deal.get("broker_name", ""),
                "Source URL":    deal.get("listing_url", ""),
                "Match Score":   deal.get("match_score", 0),
                "Green Flags":   "\n".join(green_flags),
                "Red Flags":     "\n".join(red_flags),
                "Status":        "New - Review",
                "Analysis Run":  False,
                "Date Found":    date.today().isoformat(),
            }},
            timeout=15,
        )
        if not resp.ok:
            print(f"Airtable error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Airtable error: {e}")

def send_email(deals):
    """Send the digest email."""
    from datetime import date
    today = date.today().strftime("%B %d, %Y")
    subject = f"Deal Screener: {len(deals)} new matches today" if deals else "Deal Screener: No matches today"

    cards = ""
    for d in deals:
        price     = f"${d.get('asking_price', 0):,}"
        sde       = f"${d.get('sde', 0):,}"
        score     = d.get("match_score", 0)
        source    = d.get("source_site", "Unknown source")
        url       = d.get("listing_url", "#")
        location  = d.get("location", "")

        green_flags = d.get("green_flags", [])
        red_flags   = d.get("red_flags", [])
        mismatches  = d.get("mismatches", [])

        green_html = ""
        if green_flags:
            items = "".join(f"<li>{f}</li>" for f in green_flags)
            green_html = f"""
            <div style="margin:10px 0 6px;">
              <div style="font-size:11px;font-weight:600;color:#065f46;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">✓ Green flags</div>
              <ul style="margin:0;padding-left:18px;color:#065f46;font-size:13px;line-height:1.7;">{items}</ul>
            </div>"""

        red_html = ""
        all_red = red_flags + mismatches
        if all_red:
            items = "".join(f"<li>{f}</li>" for f in all_red)
            red_html = f"""
            <div style="margin:10px 0 6px;">
              <div style="font-size:11px;font-weight:600;color:#991b1b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">✗ Red flags / mismatches</div>
              <ul style="margin:0;padding-left:18px;color:#991b1b;font-size:13px;line-height:1.7;">{items}</ul>
            </div>"""

        # Score color
        if score >= 85:
            score_bg = "#065f46"; score_color = "#ffffff"
        elif score >= 70:
            score_bg = "#1e40af"; score_color = "#ffffff"
        else:
            score_bg = "#991b1b"; score_color = "#ffffff"

        cards += f"""
        <div style="border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin-bottom:20px;background:#ffffff;">

          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;">
            <div style="flex:1;min-width:0;">
              <div style="font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">{source}</div>
              <h3 style="font-size:16px;font-weight:600;margin:0 0 3px;color:#111827;line-height:1.3;">{d.get('title', '')}</h3>
              <div style="color:#6b7280;font-size:13px;">{location}</div>
            </div>
            <div style="flex-shrink:0;background:{score_bg};color:{score_color};width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;text-align:center;">
              {score}%
            </div>
          </div>

          <div style="display:flex;gap:24px;margin:14px 0 0;padding:12px 0;border-top:1px solid #f3f4f6;border-bottom:1px solid #f3f4f6;font-size:14px;color:#374151;">
            <span><span style="color:#9ca3af;font-size:12px;">ASKING</span><br><strong>{price}</strong></span>
            <span><span style="color:#9ca3af;font-size:12px;">SDE</span><br><strong>{sde}</strong></span>
            <span><span style="color:#9ca3af;font-size:12px;">YEARS</span><br><strong>{d.get('years_in_business', '?')}</strong></span>
          </div>

          {green_html}
          {red_html}

          <div style="margin-top:14px;">
            <a href="{url}" style="display:inline-block;background:#2563eb;color:white;padding:9px 20px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:500;">View Listing →</a>
          </div>

        </div>"""

    body = f"""<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;margin:0;padding:32px 16px;">
    <div style="max-width:600px;margin:0 auto;">
      <div style="margin-bottom:24px;">
        <div style="font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">Deal Screener</div>
        <h1 style="font-size:26px;font-weight:700;color:#111827;margin:0 0 4px;">{len(deals)} new matches today</h1>
        <div style="color:#9ca3af;font-size:13px;">{today} · All scored ≥70/100</div>
      </div>
      {cards if cards else '<p style="color:#6b7280;">No listings matched today\'s criteria.</p>'}
    </div>
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

        score = deal.get("match_score") or 0
        title = (deal.get("title") or "").lower().strip()

        if score >= 70 and title not in seen_titles and title:
            seen_titles.add(title)
            matches.append(deal)
            save_to_airtable(deal)
            print(f"  ✓ MATCH: {deal.get('title')} — score {score}")
        else:
            print(f"  — No match (score: {score})")

        time.sleep(5)  # be polite to Firecrawl's free tier

    send_email(matches)
    print(f"Done. {len(matches)} matches found.")

if __name__ == "__main__":
    main()
