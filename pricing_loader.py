"""
pricing_loader.py — Fetch competitor pricing gap data from Google Sheets.

Reads the "Performance by region" tab (gid=1938268207) from each city's
pricing dashboard and extracts columns I, J, M, N:
  I = surge gap vs competitor 1, weekdays
  J = surge gap vs competitor 1, weekends
  M = surge gap vs competitor 2, weekdays
  N = surge gap vs competitor 2, weekends

Uses the public Google Sheets CSV export URL — no authentication required.
The sheets must be publicly readable ("Anyone with the link can view").
"""

import csv
import io
import urllib.request
import urllib.error

# City → Google Sheets configuration
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

PERF_SHEET_GID = 1938268207   # "Performance by region" tab gid

# Columns I, J, M, N as 0-based indices
COL_I, COL_J, COL_M, COL_N = 8, 9, 12, 13


def _csv_url(file_id, gid):
    return (
        f'https://docs.google.com/spreadsheets/d/{file_id}'
        f'/export?format=csv&gid={gid}'
    )


def _fetch_csv(url):
    """Download a CSV URL and return a list of rows (each row is a list of strings)."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode('utf-8-sig')  # strip BOM if present
    reader = csv.reader(io.StringIO(raw))
    return list(reader)


def _safe_float(val):
    """Parse a spreadsheet cell to float; returns None for blanks/errors."""
    if val is None:
        return None
    s = str(val).strip().replace('%', '').replace(',', '.').replace('\\', '')
    if not s or s in ('-', '—', '#N/A', '#REF!', '#VALUE!', '#DIV/0!', 'N/A'):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _cell(row, idx):
    return row[idx] if len(row) > idx else ''


def load_pricing_data():
    """
    Returns dict keyed by city (matching keys in PRICING_SHEETS):
    {
      'Malaga': {
        'default_region': 'Málaga',
        'regions': ['Málaga', 'Marbella', 'Airport', 'Mijas'],
        'col_headers': {'i': 'Col I label', 'j': 'Col J label',
                        'm': 'Col M label', 'n': 'Col N label'},
        'rows': [
          {'region': 'Málaga', 'i': 12.5, 'j': 18.2, 'm': -3.1, 'n': 5.0},
          ...
        ]
      },
      ...
    }
    Returns {} on complete failure.
    """
    result = {}

    for city, cfg in PRICING_SHEETS.items():
        print(f'  [pricing] Fetching {city}…', end=' ', flush=True)
        try:
            url = _csv_url(cfg['file_id'], PERF_SHEET_GID)
            all_rows = _fetch_csv(url)

            if not all_rows:
                print('empty sheet')
                continue

            # Row 0 is the header row
            header = all_rows[0]
            col_headers = {
                'i': _cell(header, COL_I) or 'Gap weekday (comp. 1)',
                'j': _cell(header, COL_J) or 'Gap weekend (comp. 1)',
                'm': _cell(header, COL_M) or 'Gap weekday (comp. 2)',
                'n': _cell(header, COL_N) or 'Gap weekend (comp. 2)',
            }

            parsed = []
            for row in all_rows[1:]:
                region = _cell(row, 0).strip()
                if not region or region.startswith('#') or region == 'NO_HEADER':
                    continue

                vi = _safe_float(_cell(row, COL_I))
                vj = _safe_float(_cell(row, COL_J))
                vm = _safe_float(_cell(row, COL_M))
                vn = _safe_float(_cell(row, COL_N))

                # Skip rows where all four values are missing
                if all(v is None for v in [vi, vj, vm, vn]):
                    continue

                parsed.append({'region': region, 'i': vi, 'j': vj, 'm': vm, 'n': vn})

            result[city] = {
                'default_region': cfg['default_region'],
                'regions': cfg['regions'],
                'col_headers': col_headers,
                'rows': parsed,
            }
            print(f'{len(parsed)} region(s) ✓')

        except urllib.error.HTTPError as e:
            print(f'HTTP {e.code} — sheet may not be public')
            result[city] = {
                'default_region': cfg['default_region'],
                'regions': cfg['regions'],
                'col_headers': {},
                'rows': [],
                'error': f'HTTP {e.code}',
            }
        except Exception as e:
            print(f'error — {e}')
            result[city] = {
                'default_region': cfg['default_region'],
                'regions': cfg['regions'],
                'col_headers': {},
                'rows': [],
                'error': str(e),
            }

    return result
