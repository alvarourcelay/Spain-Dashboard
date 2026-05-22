#!/usr/bin/env python3
"""Load budget data from the CSV export.

The spreadsheet contains TWO consecutive city blocks:
  Block 1 → Annual budget   (set at the start of the year)
  Block 2 → Monthly budget  (updated monthly to correct deviations)

Returns
-------
dict  {
    'annual':  {city: {month: {gmv, orders, asp, net_rate}}},
    'monthly': {city: {month: {gmv, orders, asp, net_rate}}},
}
  month    = 'YYYY-MM'  (e.g. '2026-01')
  gmv      = EUR (float)
  orders   = count (float)
  asp      = EUR per order (float | None if orders == 0)
  net_rate = Commission for Net Rate − Gross Supply − Gross Demand − Gross Branding (EUR)
"""

import csv, os

BUDGET_ANNUAL_CSV = os.environ.get(
    'BUDGET_ANNUAL_CSV',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'budget_annual.csv')
)

_MONTH_MAP = {
    'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
    'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12',
}

def _clean(s):
    if not s:
        return 0.0
    s = str(s).strip().replace(',', '')
    try:
        return float(s)
    except ValueError:
        return 0.0

def _col_to_month(col):
    """'Jan2026' → '2026-01', or None if unrecognised."""
    col = col.strip()
    m, y = col[:3], col[3:]
    return f"{y}-{_MONTH_MAP[m]}" if m in _MONTH_MAP and y.isdigit() else None


def _parse_block(data_rows, month_idx):
    """Parse one flat block of (city, account, val…) rows into
    {city: {account: [val_per_month]}}, stopping when a city is encountered
    for the second time in the same block (which marks the start of the next block).

    Returns (city_accounts, remaining_rows).
    """
    city_accounts = {}
    city_order = []      # preserves first-seen order to detect restart

    for i, row in enumerate(data_rows):
        if not row or not row[0].strip():
            continue
        city    = row[0].strip()
        account = row[1].strip() if len(row) > 1 else ''
        if not account:
            continue

        # Detect restart of city sequence → end of current block
        if city in city_accounts and city not in city_order[-1:]:
            # This city already appeared AND the previous row was a different city
            # which means we've looped back — return what we have so far
            return city_accounts, data_rows[i:]

        city_accounts.setdefault(city, {})[account] = [
            _clean(row[j]) if j < len(row) else 0.0
            for j, _ in month_idx
        ]
        if city not in city_accounts or city not in [c for c in city_order]:
            city_order.append(city)

    return city_accounts, []


def _build_result(city_accounts, month_idx):
    """Convert {city: {account: [vals]}} → {city: {month: metrics}}."""
    result = {}
    n_months = len(month_idx)

    for city, accounts in city_accounts.items():
        def _get(name):
            vals = accounts.get(name, [])
            return (vals + [0.0] * n_months)[:n_months]

        gmv_v      = _get('GMV')
        orders_v   = _get('No. of rides/orders')
        # Net Rate = Commission for Net Rate − Gross Supply Spend − Gross Demand Spend − Gross Branding Spend
        comm_v     = _get('Commission for Net Rate')
        supply_v   = _get('Gross Supply Spend')
        demand_v   = _get('Gross Demand Spend')
        branding_v = _get('Gross Branding Spend')   # zeros if absent

        city_result = {}
        for i, (_, month) in enumerate(month_idx):
            gmv      = gmv_v[i]
            orders   = orders_v[i]
            net_rate = comm_v[i] - supply_v[i] - demand_v[i] - branding_v[i]
            asp      = round(gmv / orders, 4) if orders > 0 else None

            city_result[month] = {
                'gmv':      gmv,
                'orders':   orders,
                'asp':      asp,
                'net_rate': net_rate,
            }

        result[city] = city_result

    return result


def load_budget_data(csv_path=None):
    """Return {'annual': {...}, 'monthly': {...}}."""
    path = csv_path or BUDGET_ANNUAL_CSV
    result = {'annual': {}, 'monthly': {}}

    with open(path, encoding='utf-8') as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    # ── Locate header row ─────────────────────────────────────────────────────
    header = None
    data_start = 0
    for i, row in enumerate(all_rows):
        if row and row[0].strip() == 'city':
            header = row
            data_start = i + 1
            break

    if not header:
        print('budget_loader: header row not found — returning empty dict')
        return result

    # ── Build month index ─────────────────────────────────────────────────────
    month_idx = []
    for j, col in enumerate(header):
        if j < 2:
            continue
        m = _col_to_month(col)
        if m:
            month_idx.append((j, m))

    if not month_idx:
        print('budget_loader: no month columns found')
        return result

    # ── Parse the two consecutive blocks ─────────────────────────────────────
    data_rows = [r for r in all_rows[data_start:] if r]  # skip blank lines

    block1_accounts, remaining = _parse_block(data_rows, month_idx)
    block2_accounts, _         = _parse_block(remaining, month_idx)

    result['annual']  = _build_result(block1_accounts, month_idx)
    result['monthly'] = _build_result(block2_accounts, month_idx)

    n1, n2 = len(result['annual']), len(result['monthly'])
    print(f'budget_loader: annual={n1} cities, monthly={n2} cities, {len(month_idx)} months each')
    return result


if __name__ == '__main__':
    d = load_budget_data()
    for btype in ('annual', 'monthly'):
        print(f'\n=== {btype.upper()} BUDGET ===')
        for city in list(d[btype].keys())[:1]:
            print(f'{city}:')
            for month, vals in sorted(d[btype][city].items()):
                print(f'  {month}: GMV={vals["gmv"]:>10,.0f}  '
                      f'orders={vals["orders"]:>7,.0f}  '
                      f'ASP={str(round(vals["asp"],2)) if vals["asp"] else "—":>7}  '
                      f'NR={vals["net_rate"]:>10,.0f}')
