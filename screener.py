
import email
import hashlib
import html
import imaplib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from sources import get_sources

load_dotenv()

EASTERN = ZoneInfo("America/New_York")
EXPECTED_GMAIL = "kushagra.gv@gmail.com"
DEALOS_BASE_URL = os.environ.get(
    "DEALOS_BASE_URL", "https://kush-sba-deal-os.kgali01.chatgpt.site"
).rstrip("/")
ALERT_TERMS = (
    "business for sale",
    "listing alert",
    "buyer match",
    "search agent",
    "cash flow",
    "seller discretionary",
    "sde",
    "asking price",
    "acquisition opportunity",
    "bizbuysell",
    "bizquest",
    "dealstream",
    "transworld",
    "sunbelt",
)
TARGET_STATE_NAMES = (
    "new jersey",
    "new york",
    "connecticut",
    "massachusetts",
    "maryland",
    "california",
)
TARGET_STATE_ABBRS = ("NJ", "NY", "CT", "MA", "MD", "CA")
FINANCIAL_TERMS = (
    "$",
    "asking",
    "price",
    "cash flow",
    "sde",
    "seller discretionary",
    "ebitda",
    "revenue",
    "gross sales",
)
TRACKING_QUERY_PREFIXES = ("utm_", "mc_", "trk", "tracking")
SCREEN_TIMEOUT_SECONDS = 120
INGEST_TIMEOUT_SECONDS = 180
INGEST_ATTEMPTS = 3


class IntegrationError(RuntimeError):
    pass


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise IntegrationError(f"Required environment value {name} is missing.")
    return value


def now_eastern():
    return datetime.now(EASTERN)


def iso_eastern(value=None):
    return (value or now_eastern()).isoformat(timespec="seconds")


def has_state_signal(text):
    lower = text.lower()
    if any(state in lower for state in TARGET_STATE_NAMES):
        return True
    return any(re.search(rf"\b{abbr}\b", text, re.IGNORECASE) for abbr in TARGET_STATE_ABBRS)


def should_screen_source(text, source):
    haystack = f"{source.get('url', '')} {source.get('source', '')} {text}"
    has_financials = any(term in haystack.lower() for term in FINANCIAL_TERMS)
    return has_financials and has_state_signal(haystack)


def scrape_source(session, source, firecrawl_key):
    try:
        response = session.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {firecrawl_key}"},
            json={
                "url": source["url"],
                "formats": ["markdown"],
                "onlyMainContent": True,
                "timeout": 45000,
            },
            timeout=60,
        )
        if response.status_code == 429:
            return "", "Firecrawl credit or rate limit reached", True
        if not response.ok:
            try:
                data = response.json()
                detail = data.get("error") or data.get("message")
            except ValueError:
                detail = response.text[:200]
            return "", f"HTTP {response.status_code}: {detail or 'scrape failed'}", False
        markdown = response.json().get("data", {}).get("markdown", "")
        if len(markdown.strip()) < 100:
            return "", "No usable listing content returned", False
        return markdown[:60_000], None, False
    except requests.RequestException as exc:
        return "", f"Request failed: {exc.__class__.__name__}", False


def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-github-repository": os.environ.get(
            "GITHUB_REPOSITORY", "darkmobster/deal-screener"
        ),
        "x-github-event": os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch"),
    }


def screen_material(session, token, channel, source_name, source_url, material):
    try:
        response = session.post(
            f"{DEALOS_BASE_URL}/api/monitor-screen",
            headers=github_headers(token),
            json={
                "channel": channel,
                "sourceName": source_name,
                "sourceUrl": source_url,
                "material": material[:60_000],
            },
            timeout=SCREEN_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise IntegrationError(
            f"DealOS screening timed out after {SCREEN_TIMEOUT_SECONDS} seconds"
        ) from exc
    except requests.RequestException as exc:
        raise IntegrationError(
            f"DealOS screening request failed: {exc.__class__.__name__}"
        ) from exc
    if not response.ok:
        try:
            detail = response.json().get("error")
        except ValueError:
            detail = response.text[:300]
        raise IntegrationError(
            f"DealOS screening returned HTTP {response.status_code}: {detail or 'unknown error'}"
        )
    candidates = response.json().get("candidates", [])
    if not isinstance(candidates, list):
        raise IntegrationError("DealOS screening returned an invalid candidates array.")
    return candidates


def plain_text_from_message(message):
    plain_parts = []
    html_parts = []
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if content_type == "text/plain":
            plain_parts.append(text)
        else:
            html_parts.append(text)
    if plain_parts:
        return "\n".join(plain_parts)
    raw_html = "\n".join(html_parts)
    without_tags = re.sub(r"<[^>]+>", " ", raw_html)
    return html.unescape(re.sub(r"\s+", " ", without_tags))


def extract_urls(text):
    return re.findall(r"https?://[^\s<>\"']+", text or "")[:20]


def source_name_from_email(sender, subject):
    sender_match = re.search(r"@([A-Za-z0-9.-]+)", sender or "")
    domain = sender_match.group(1).lower() if sender_match else ""
    if domain:
        return domain.removeprefix("mail.").removeprefix("email.")
    return (subject or "Gmail listing alert")[:120]


def fetch_gmail_alerts(since_at):
    gmail_user = os.environ.get("GMAIL_USER", "").strip().lower()
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if gmail_user != EXPECTED_GMAIL:
        return "failed", [], f"Gmail account mismatch; expected {EXPECTED_GMAIL}"
    if not gmail_password:
        return "failed", [], "Gmail app password is missing"

    messages = []
    try:
        with imaplib.IMAP4_SSL("imap.gmail.com", 993) as mailbox:
            mailbox.login(gmail_user, gmail_password)
            status, _ = mailbox.select("INBOX", readonly=True)
            if status != "OK":
                raise IntegrationError("Gmail inbox could not be opened read-only.")
            since_day = since_at.astimezone(EASTERN).strftime("%d-%b-%Y")
            status, data = mailbox.search(None, "SINCE", since_day)
            if status != "OK":
                raise IntegrationError("Gmail search failed.")
            message_ids = data[0].split()[-100:]
            for message_id in message_ids:
                status, fetched = mailbox.fetch(message_id, "(RFC822)")
                if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                    continue
                parsed = email.message_from_bytes(fetched[0][1])
                subject = str(parsed.get("Subject", ""))
                sender = str(parsed.get("From", ""))
                sender_name, sender_email = parseaddr(sender)
                body = plain_text_from_message(parsed)
                haystack = f"{subject}\n{sender}\n{body}".lower()
                if not any(term in haystack for term in ALERT_TERMS):
                    continue
                try:
                    discovered = parsedate_to_datetime(str(parsed.get("Date", "")))
                    if discovered.tzinfo is None:
                        discovered = discovered.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    discovered = now_eastern()
                if discovered.astimezone(timezone.utc) < since_at.astimezone(timezone.utc):
                    continue
                urls = extract_urls(body)
                messages.append(
                    {
                        "sourceName": source_name_from_email(sender, subject),
                        "senderName": sender_name or sender_email or "Unknown sender",
                        "senderEmail": sender_email.lower() or None,
                        "sourceUrl": urls[0] if urls else None,
                        "externalId": str(parsed.get("Message-ID", "")).strip(),
                        "discoveredAt": discovered.astimezone(EASTERN).isoformat(
                            timespec="seconds"
                        ),
                        "material": (
                            f"Subject: {subject}\nFrom: {sender}\n"
                            f"Date: {discovered.isoformat()}\n\n{body}"
                        )[:60_000],
                    }
                )
        return "connected", messages, None
    except (imaplib.IMAP4.error, OSError, IntegrationError) as exc:
        return "failed", [], f"Gmail read failed: {exc}"


def get_previous_successful_run(session):
    try:
        response = session.get(f"{DEALOS_BASE_URL}/api/workspace", timeout=30)
        response.raise_for_status()
        raw = response.json().get("emailMonitor", {}).get("lastCheckedAt")
        if raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (requests.RequestException, ValueError, TypeError):
        pass
    return now_eastern() - timedelta(days=7)


def optional_number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def normalize_candidate(raw, channel, source_name, source_url, metadata=None):
    metadata = metadata or {}
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    disposition = str(raw.get("disposition") or "review").lower()
    if disposition not in {"qualified", "review", "disqualified"}:
        disposition = "review"
    broker_values = {
        "name": str(
            raw.get("brokerName")
            or (metadata.get("senderName") if channel == "gmail" else "")
            or ""
        ).strip(),
        "organization": str(raw.get("brokerOrganization") or "").strip(),
        "email": str(
            raw.get("brokerEmail")
            or (metadata.get("senderEmail") if channel == "gmail" else "")
            or ""
        ).strip().lower() or None,
        "phone": str(raw.get("brokerPhone") or "").strip() or None,
    }
    broker = None
    if any(broker_values.values()):
        broker_values["name"] = broker_values["name"] or "Unknown broker"
        broker_values["organization"] = (
            broker_values["organization"] or source_name
        )
        broker = broker_values
    confidence = optional_number(raw.get("confidence"))
    return {
        "externalId": str(
            raw.get("externalId") or metadata.get("externalId") or ""
        ).strip()
        or None,
        "channel": channel,
        "sourceId": None,
        "sourceName": source_name,
        "canonicalUrl": str(raw.get("canonicalUrl") or source_url or "").strip()
        or None,
        "title": title,
        "industry": str(raw.get("industry") or "Undisclosed").strip(),
        "city": str(raw.get("city") or "Undisclosed").strip(),
        "state": str(raw.get("state") or "NA").strip().upper()[:2],
        "askingPrice": optional_number(raw.get("askingPrice")),
        "revenue": optional_number(raw.get("revenue")),
        "sde": optional_number(raw.get("sde")),
        "dscr": optional_number(raw.get("dscr")),
        "disposition": disposition,
        "confidence": min(1.0, max(0.0, confidence if confidence is not None else 0.5)),
        "greenFlags": [str(item).strip() for item in raw.get("greenFlags", []) if str(item).strip()],
        "redFlags": [str(item).strip() for item in raw.get("redFlags", []) if str(item).strip()],
        "dealBreakers": [str(item).strip() for item in raw.get("dealBreakers", []) if str(item).strip()],
        "fitSummary": str(raw.get("fitSummary") or "Requires acquisition review.").strip(),
        "originContactName": (
            str(metadata.get("senderName") or "").strip() or None
            if channel == "gmail"
            else None
        ),
        "originContactEmail": (
            str(metadata.get("senderEmail") or "").strip().lower() or None
            if channel == "gmail"
            else None
        ),
        "discoveredAt": str(
            raw.get("discoveredAt") or metadata.get("discoveredAt") or ""
        ).strip()
        or None,
        "broker": broker,
    }


def canonicalize_url(url):
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith(TRACKING_QUERY_PREFIXES)
        ]
        return urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), "")
        )
    except ValueError:
        return url.strip().lower()


def candidate_fingerprint(candidate):
    canonical = canonicalize_url(candidate.get("canonicalUrl"))
    if canonical:
        return f"url:{canonical}"
    title = re.sub(r"\s+", " ", candidate.get("title", "").strip().lower())
    return "|".join(
        [title, candidate.get("state", ""), str(candidate.get("askingPrice") or "")]
    )


def add_deduplicated(candidate, candidates, seen):
    fingerprint = candidate_fingerprint(candidate)
    if fingerprint in seen:
        duplicate = dict(candidate)
        duplicate["disposition"] = "duplicate"
        duplicate["fitSummary"] = "Duplicate of another candidate in this monitor run."
        candidates.append(duplicate)
        return
    seen.add(fingerprint)
    candidates.append(candidate)


def write_payload(payload, path="monitor-run.json"):
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def post_monitor_run(session, token, payload):
    last_error = "DealOS ingestion failed without a response."
    for attempt in range(1, INGEST_ATTEMPTS + 1):
        try:
            response = session.post(
                f"{DEALOS_BASE_URL}/api/monitor-ingest",
                headers=github_headers(token),
                json=payload,
                timeout=INGEST_TIMEOUT_SECONDS,
            )
            if response.status_code in (200, 201):
                return response.json()
            try:
                detail = response.json().get("error")
            except ValueError:
                detail = response.text[:300]
            last_error = (
                f"DealOS ingestion returned HTTP {response.status_code}: "
                f"{detail or 'unknown error'}"
            )
        except requests.Timeout:
            last_error = (
                f"DealOS ingestion timed out after {INGEST_TIMEOUT_SECONDS} seconds"
            )
        except requests.RequestException as exc:
            last_error = (
                f"DealOS ingestion request failed: {exc.__class__.__name__}"
            )
        if attempt < INGEST_ATTEMPTS:
            time.sleep(2**attempt)
    raise IntegrationError(
        f"{last_error} after {INGEST_ATTEMPTS} attempts; retain the payload for retry."
    )


def run():
    token = required_env("GITHUB_TOKEN")
    firecrawl_key = required_env("FIRECRAWL_API_KEY")
    started = now_eastern()
    run_id = f"github-actions-{os.environ.get('GITHUB_RUN_ID') or hashlib.sha256(started.isoformat().encode()).hexdigest()[:16]}"
    session = requests.Session()
    write_payload(
        {
            "runId": run_id,
            "startedAt": iso_eastern(started),
            "completedAt": iso_eastern(started),
            "status": "partial",
            "gmailStatus": "pending",
            "gmailAccount": EXPECTED_GMAIL,
            "sourcesChecked": [],
            "sourcesFailed": ["The run did not reach final payload generation."],
            "summary": "Run started; this checkpoint is retained only if execution fails.",
            "candidates": [],
        }
    )
    previous_run = get_previous_successful_run(session)
    candidates = []
    seen = set()
    sources_checked = []
    sources_failed = []

    gmail_status, alerts, gmail_error = fetch_gmail_alerts(previous_run)
    if gmail_error:
        sources_failed.append(gmail_error)
    selected_alerts = alerts[:50]
    for alert_index, alert in enumerate(selected_alerts, start=1):
        source_name = alert["sourceName"]
        sources_checked.append(f"Gmail: {source_name}")
        print(
            f"[gmail {alert_index}/{len(selected_alerts)}] "
            f"Screening {source_name}"
        )
        try:
            raw_candidates = screen_material(
                session,
                token,
                "gmail",
                source_name,
                alert.get("sourceUrl"),
                alert["material"],
            )
            for raw in raw_candidates:
                candidate = normalize_candidate(
                    raw, "gmail", source_name, alert.get("sourceUrl"), alert
                )
                if candidate:
                    add_deduplicated(candidate, candidates, seen)
        except IntegrationError as exc:
            failure = f"Gmail: {source_name} ({exc})"
            sources_failed.append(failure)
            print(f"  Partial source failure: {failure}")

    listing_sources = get_sources()
    for source_index, source in enumerate(listing_sources, start=1):
        source_name = source["source"]
        sources_checked.append(source_name)
        print(
            f"[source {source_index}/{len(listing_sources)}] "
            f"Collecting {source_name}"
        )
        material, scrape_error, stop_scraping = scrape_source(
            session, source, firecrawl_key
        )
        if scrape_error:
            failure = f"{source_name}: {scrape_error}"
            sources_failed.append(failure)
            print(f"  Partial source failure: {failure}")
            if stop_scraping:
                break
            continue
        if not should_screen_source(material, source):
            continue
        try:
            raw_candidates = screen_material(
                session,
                token,
                "website",
                source_name,
                source["url"],
                material,
            )
            for raw in raw_candidates:
                candidate = normalize_candidate(
                    raw, "website", source_name, source["url"]
                )
                if candidate:
                    add_deduplicated(candidate, candidates, seen)
        except IntegrationError as exc:
            failure = f"{source_name}: {exc}"
            sources_failed.append(failure)
            print(f"  Partial source failure: {failure}")
        time.sleep(1)

    completed = now_eastern()
    counts = {
        status: sum(1 for item in candidates if item["disposition"] == status)
        for status in ("qualified", "review", "disqualified", "duplicate")
    }
    status = "partial" if sources_failed else "completed"
    payload = {
        "runId": run_id,
        "startedAt": iso_eastern(started),
        "completedAt": iso_eastern(completed),
        "status": status,
        "gmailStatus": gmail_status,
        "gmailAccount": EXPECTED_GMAIL,
        "sourcesChecked": list(dict.fromkeys(sources_checked)),
        "sourcesFailed": sources_failed,
        "summary": (
            f"GitHub Actions screened Gmail and {len(sources_checked)} source checks. "
            f"Results: {counts['qualified']} qualified, {counts['review']} review, "
            f"{counts['disqualified']} disqualified, {counts['duplicate']} duplicate."
        ),
        "candidates": candidates,
    }
    write_payload(payload)
    result = post_monitor_run(session, token, payload)
    print(
        "DealOS ingestion succeeded: "
        f"runId={result.get('runId')} qualified={counts['qualified']} "
        f"review={counts['review']} disqualified={counts['disqualified']} "
        f"duplicates={counts['duplicate']}"
    )
    return result


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Deal screener failed: {exc}", file=sys.stderr)
        sys.exit(1)

