import os, requests
from datetime import date
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.environ["AIRTABLE_API_KEY"]
BASE_ID  = os.environ["AIRTABLE_BASE_ID"]
TABLE_ID = os.environ["AIRTABLE_DEALS_TABLE_ID"]
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ── Create dummy record ──────────────────────────────────
print("Creating dummy record...")
payload = {"fields": {
    "Deal Name":    "TEST - Dummy Pest Control Company",
    "Asking Price": 1500000,
    "SDE":          450000,
    "Industry":     "Pest Control",
    "State":        "FL",
    "Source URL":   "https://example.com/test-listing",
    "Match Score":  85,
    "Green Flags":  "Absentee owner\nSeller financing available",
    "Red Flags":    "Single key employee",
    "Status":       "New - Review",  # must match exact option name in Airtable
    "Analysis Run": False,
    "Date Found":   date.today().isoformat(),
}}

create_resp = requests.post(BASE_URL, headers=HEADERS, json=payload, timeout=15)
if not create_resp.ok:
    print(f"FAIL — could not create record: {create_resp.status_code} {create_resp.text}")
    raise SystemExit(1)

record_id = create_resp.json()["id"]
print(f"  Created record: {record_id}")

# ── Read it back ─────────────────────────────────────────
print("Reading record back...")
get_resp = requests.get(f"{BASE_URL}/{record_id}", headers=HEADERS, timeout=15)
if not get_resp.ok:
    print(f"FAIL — could not read record: {get_resp.status_code} {get_resp.text}")
    raise SystemExit(1)

fields = get_resp.json()["fields"]
print("  Confirmed fields:")
for key, val in fields.items():
    print(f"    {key}: {val}")

print("\nPASS — record created and read back successfully.")
print(f"Note: delete test record {record_id} from Airtable manually if needed.")
