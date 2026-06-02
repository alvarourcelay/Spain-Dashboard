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
  CAST(week_start AS STRING)           AS week_start,
  city_name,
  competitor_app,
  digital_market_share_rides_raw       AS market_share
FROM hive_metastore.dbt_yaqub_mcreddie_spark.mart_fox_market_weekly_city
WHERE country_name = 'Spain'
  AND week_start >= '{start_date}'
  AND digital_market_share_rides_raw IS NOT NULL
ORDER BY week_start, city_name, competitor_app
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
        city  = r['city_name']
        week  = r['week_start']          # 'YYYY-MM-DD' (Monday)
        comp  = _normalise_comp(r['competitor_app'])
        share = r['market_share']

        if comp is None or share is None:
            continue

        try:
            share_pct = round(float(share) * 100, 1)
        except (TypeError, ValueError):
            continue

        data.setdefault(city, {}).setdefault(week, {})[comp] = share_pct

    return data
