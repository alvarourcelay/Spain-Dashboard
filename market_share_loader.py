"""
Market share loader for Bolt Spain dashboard.
Source: hive_metastore.dbt_yaqub_mcreddie_spark.mart_fox_market_weekly_city
        (FoxIntelligence weekly per-competitor market share)

Returns:
    {
      "Madrid": {
        "2025-01-06": {"Bolt": 13.5, "Uber": 70.1, "Cabify": 14.2, "Freenow": 2.2},
        "2025-01-13": { ... },
        ...
      },
      "Barcelona": { ... },
      ...
    }
"""

import os

DATABRICKS_HOST      = os.environ['DATABRICKS_HOST']
DATABRICKS_TOKEN     = os.environ['DATABRICKS_TOKEN']
DATABRICKS_HTTP_PATH = os.environ['DATABRICKS_HTTP_PATH']

START_DATE = '2025-01-01'

# Competitor display names (normalise whatever the mart uses)
COMP_NAMES = {
    'bolt':     'Bolt',
    'uber':     'Uber',
    'cabify':   'Cabify',
    'freenow':  'Freenow',
    'free now': 'Freenow',
    'heetch':   'Heetch',
    'mytaxi':   'Freenow',   # rebranded
}

SQL = """
SELECT
  week                                 AS week_start,
  city,
  merchant,
  market_share_rides                   AS market_share
FROM hive_metastore.rides_finance.foxintel_enriched
WHERE lower(country) = 'spain'
  AND week >= '{start_date}'
  AND market_share_rides IS NOT NULL
ORDER BY week, city, merchant
""".strip()


def _normalise_comp(name):
    """Normalise competitor app name to display name."""
    if name is None:
        return None
    key = name.strip().lower()
    return COMP_NAMES.get(key, name.strip().title())


def load_market_share():
    from databricks import sql as dbsql

    conn = dbsql.connect(
        server_hostname = DATABRICKS_HOST,
        http_path       = DATABRICKS_HTTP_PATH,
        access_token    = DATABRICKS_TOKEN,
    )

    query = SQL.format(start_date=START_DATE)
    print(f"Querying FoxIntelligence market share from {START_DATE}…")

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    conn.close()
    print(f"  → {len(rows)} city-week-competitor rows returned")

    # Build nested dict: city → week_start → { competitor: share% }
    data = {}
    for row in rows:
        r = dict(zip(cols, row))
        city  = r['city']
        week  = r['week_start']          # 'YYYY-MM-DD' (Monday)
        comp  = _normalise_comp(r['merchant'])
        share = r['market_share']

        if comp is None or share is None:
            continue

        try:
            share_pct = round(float(share) * 100, 1)
        except (TypeError, ValueError):
            continue

        data.setdefault(city, {}).setdefault(week, {})[comp] = share_pct

    return data
