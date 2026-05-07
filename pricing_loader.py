"""
pricing_loader.py — Fetch competitor pricing gap data from Google Sheets.

Sheet structure (per city):
  - Row 0:   top-level header ("Week actual", etc.)
  - Row 1:   region names  (Málaga, Airport, …) — one per 14-column block
  - Row 2:   competitor labels (Uber, Cabify, …)
  - Row 3:   surge labels
  - Row 4:   Weekdays / Weekend column labels
  - Row 5+:  data rows  (col A = date YYYY-MM-DD, col B = week label W##'YY)

Each region occupies a block of BLOCK_SIZE (14) columns starting at FIRST_BLOCK_COL (2 = col C).
Within each block the 4 columns of interest are at relative positions:
  +6  → Uber    weekday  gap  (col I in block-0 / Málaga)
  +7  → Uber    weekend  gap  (col J)
  +10 → Cabify  weekday  gap  (col M)
  +11 → Cabify  weekend  gap  (col N)

Uses the public Google Sheets CSV export — no authentication required.
All sheets must be publicly readable ("Anyone with the link can view").
"""

import csv
import io
import urllib.request
import urllib.error

# ── Sheet configuration ──────────────────────────────────────────────────────
PRICING_SHEETS = {
    'Malaga': {
        'file_id': '16znqUuFQkNAmI6taEwrmgMLrd12mUaJox0FywaFjgTg',
        'default_region': 'Málaga',
        'regions': ['Málaga', 'Marbella', 'Airport', 'Mijas'],
    },
    'Sevilla': {
        'file_id': '1EDQtYYyOGojBp-o2sv-pnrebDVEbtOoTO_MEv9joLOs',
        'default_region': 'Sevilla',
        'regions': ['Sevilla'],
    },
    'Zaragoza': {
        'file_id': '1EVmHA-1YLqMOgMsVMjfENjgDBx8QEhKPLmNBFxbeIds',
        'default_region': 'Zaragoza',
        'regions': ['Zaragoza'],
    },
    'Murcia': {
        'file_id': '1y5mtLSEU1ShZmpwLFj3Jo64InBDSBwqPajBaUO5etQE',
        'default_region': 'Murcia',
        'regions': ['Murcia'],
    },
    'A Coruña': {
        'file_id': '1sZyRXmhNCykulkWspnifzVSl9ztr6y1eVvZZYRzVn4Q',
        'default_region': 'A Coruña',
        'regions': ['A Coruña'],
    },
    'Barcelona': {
        'file_id': '1NRJABFmNT596o7BQSMU32N3LdLtNw64_omSu4JyuiIY',
        'default_region': 'Barcelona',
        'regions': ['Barcelona', 'Barcelona Airport', 'Sabadell', 'Rubi'],
    },
}

PERF_SHEET_GID  = 1938268207  # "Performance by region" tab

BLOCK_SIZE      = 14   # columns per region block
FIRST_BLOCK_COL = 2    # col C (0-indexed) = start of first block

# Relative positions inside each block (0-indexed from block start)
REL_UBER_WD = 6   # Uber    weekday  (col I in block-0)
REL_UBER_WE = 7   # Uber    weekend  (col J)
REL_CAB_WD  = 10  # Cabify  weekday  (col M)
REL_CAB_WE  = 11  # Cabify  weekend  (col N)

DATA_START_ROW = 5   # 0-indexed; rows 0-4 are header rows


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


def _safe_float(val):
    if val is None:
        return None
    s = str(val).strip().replace('%', '').replace(',', '.').replace('\\', '')
    if not s or s in ('-', '—', '#N/A', '#REF!', '#VALUE!', '#DIV/0!', 'N/A', '#DIV/0'):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _cell(row, idx):
    return row[idx] if len(row) > idx else ''


def _is_date(s):
    """True if the string looks like a YYYY-MM-DD date."""
    s = s.strip()
    return len(s) >= 8 and s[0].isdigit() and '-' in s


# ── Main loader ───────────────────────────────────────────────────────────────
def load_pricing_data():
    """
    Returns:
    {
      'Malaga': {
        'default_region': 'Málaga',
        'regions': ['Málaga', 'Marbella', 'Airport', 'Mijas'],
        'data': {
          'Málaga': [
            {'date': '2025-11-10', 'week': "W46'25",
             'uber_wd': -12.3, 'uber_we': 10.1,
             'cab_wd':  -5.2,  'cab_we':   3.1},
            ...
          ],
          'Marbella': [...],
          ...
        }
      },
      ...
    }
    """
    result = {}

    for city, cfg in PRICING_SHEETS.items():
        print(f'  [pricing] Fetching {city}…', end=' ', flush=True)
        try:
            url = _csv_url(cfg['file_id'], PERF_SHEET_GID)
            all_rows = _fetch_csv(url)

            regions = cfg['regions']
            data_by_region = {}

            for r_idx, region in enumerate(regions):
                block_start  = FIRST_BLOCK_COL + r_idx * BLOCK_SIZE
                col_uber_wd  = block_start + REL_UBER_WD
                col_uber_we  = block_start + REL_UBER_WE
                col_cab_wd   = block_start + REL_CAB_WD
                col_cab_we   = block_start + REL_CAB_WE

                region_rows = []
                for row in all_rows[DATA_START_ROW:]:
                    date_val = _cell(row, 0).strip()
                    week_val = _cell(row, 1).strip()

                    if not _is_date(date_val):
                        continue

                    uber_wd = _safe_float(_cell(row, col_uber_wd))
                    uber_we = _safe_float(_cell(row, col_uber_we))
                    cab_wd  = _safe_float(_cell(row, col_cab_wd))
                    cab_we  = _safe_float(_cell(row, col_cab_we))

                    if all(v is None for v in [uber_wd, uber_we, cab_wd, cab_we]):
                        continue

                    region_rows.append({
                        'date':    date_val,
                        'week':    week_val,
                        'uber_wd': uber_wd,
                        'uber_we': uber_we,
                        'cab_wd':  cab_wd,
                        'cab_we':  cab_we,
                    })

                data_by_region[region] = region_rows

            total = sum(len(v) for v in data_by_region.values())
            print(f'{total} data points across {len(regions)} region(s) ✓')

            result[city] = {
                'default_region': cfg['default_region'],
                'regions':        regions,
                'data':           data_by_region,
            }

        except urllib.error.HTTPError as e:
            print(f'HTTP {e.code} — sheet may not be public')
            result[city] = {
                'default_region': cfg['default_region'],
                'regions':        cfg['regions'],
                'data':           {},
                'error':          f'HTTP {e.code}',
            }
        except Exception as e:
            print(f'error — {e}')
            result[city] = {
                'default_region': cfg['default_region'],
                'regions':        cfg['regions'],
                'data':           {},
                'error':          str(e),
            }

    return result
