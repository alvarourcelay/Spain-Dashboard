"""
quality_loader.py — Fetch quality metrics from Google Sheets (Looker export).

Sheet structure (tab gid=1388752149):
  Row 0:  header  →  Date | City | % of Order Tries Outside Search Radius |
                      Acceptance Rate Inside Search Radius % |
                      Acceptance Rate Outside Search Radius %
  Row 1+: data rows, one row per city per day

Date values: YYYY-MM-DD
Value format: "45.00%" (string with % sign, needs stripping)
Coverage:     2025-01-01 onwards, daily, ~11 Spain cities

Uses the public Google Sheets CSV export — no authentication required.
Sheet must be publicly readable ("Anyone with the link can view").
"""

import csv
import io
import urllib.request
import urllib.error

# ── Sheet configuration ──────────────────────────────────────────────────────
QUALITY_FILE_ID = '1AoRw2IpUAbzicyivZbhIjHTz6tHX4vr3rHDuSAkE-RA'
QUALITY_GID     = 1388752149   # the only tab

# Column indices (0-based)
COL_DATE     = 0
COL_CITY     = 1
COL_OOT_GS   = 2   # % of Order Tries Outside Search Radius
COL_AR_IN    = 3   # Acceptance Rate Inside Search Radius %
COL_AR_OUT   = 4   # Acceptance Rate Outside Search Radius %


# ── Helpers ──────────────────────────────────────────────────────────────────
def _csv_url(file_id, gid):
    return (
        f'https://docs.google.com/spreadsheets/d/{file_id}'
        f'/export?format=csv&gid={gid}'
    )


def _fetch_csv(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode('utf-8-sig')
    reader = csv.reader(io.StringIO(raw))
    return list(reader)


def _safe_pct(val):
    """Parse '45.00%' → 45.0  (percentage as float, not as fraction)."""
    if val is None:
        return None
    s = str(val).strip().replace('%', '').replace(',', '.').strip()
    if not s or s in ('-', '—', '#N/A', '#REF!', '#VALUE!', '#DIV/0!', 'N/A'):
        return None
    try:
        return round(float(s), 4)
    except ValueError:
        return None


def _cell(row, idx):
    return row[idx] if len(row) > idx else ''


def _is_date(s):
    s = s.strip()
    return len(s) >= 8 and s[0].isdigit() and '-' in s


# ── Main loader ───────────────────────────────────────────────────────────────
def load_quality_data():
    """
    Returns:
    {
      'Madrid': {
        '2025-01-01': {'oot_gs': 45.0, 'ar_in': 82.5, 'ar_out': 61.3},
        '2025-01-02': {...},
        ...
      },
      'Malaga': { ... },
      ...
    }

    All percentage values are stored as floats (e.g. 45.0 means 45%).
    Missing values are stored as None.
    """
    url = _csv_url(QUALITY_FILE_ID, QUALITY_GID)
    print('  [quality] Fetching from Google Sheet…', end=' ', flush=True)

    try:
        all_rows = _fetch_csv(url)
        result   = {}
        n        = 0

        for row in all_rows[1:]:   # skip header row
            date = _cell(row, COL_DATE).strip()
            city = _cell(row, COL_CITY).strip()

            if not date or not city:
                continue
            if not _is_date(date):
                continue

            oot_gs = _safe_pct(_cell(row, COL_OOT_GS))
            ar_in  = _safe_pct(_cell(row, COL_AR_IN))
            ar_out = _safe_pct(_cell(row, COL_AR_OUT))

            # Skip rows where all three values are missing
            if oot_gs is None and ar_in is None and ar_out is None:
                continue

            if city not in result:
                result[city] = {}
            result[city][date] = {
                'oot_gs': oot_gs,
                'ar_in':  ar_in,
                'ar_out': ar_out,
            }
            n += 1

        print(f'{n} rows across {len(result)} cities ✓')
        return result

    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code} — sheet may not be public')
        return {}
    except Exception as e:
        print(f'error — {e}')
        return {}
