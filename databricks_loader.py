"""
Databricks data loader for Bolt Spain dashboard.
Queries mart_city_hour_local_rides + mart_non_additive_city_hour_local_rides
and returns a list of daily city-level records matching the CSV schema.
"""

import os
from datetime import datetime, timedelta

DATABRICKS_HOST     = os.environ['DATABRICKS_HOST']       # bolt-common.cloud.databricks.com
DATABRICKS_TOKEN    = os.environ['DATABRICKS_TOKEN']
DATABRICKS_HTTP_PATH = os.environ['DATABRICKS_HTTP_PATH'] # /sql/1.0/warehouses/...

# Pull data starting from the earliest launch date
START_DATE = '2025-01-01'

SQL = """
SELECT
  CAST(a.calendar_date_local AS STRING)                                                                    AS d,
  a.city_name                                                                                              AS c,

  -- Direct sums (additive)
  SUM(a.rides_orders_in_finished_state_local)                                                              AS f,
  SUM(CAST(a.rides_gmv_before_discounts_eur_local          AS DOUBLE))                                    AS g,
  SUM(a.sum_driver_online_time_seconds_local)                                                              AS o_sec,
  SUM(a.count_rides_sessions_local)                                                                        AS sess,
  SUM(a.rides_partners_activated_in_city_local)                                                            AS pa,
  SUM(a.rides_users_activated_in_city_local)                                                               AS nra,
  SUM(a.rides_orders_count_local)                                                                          AS orders,
  SUM(a.rides_paid_time_seconds_local)                                                                     AS paid_sec,
  SUM(a.sum_driver_waiting_orders_time_seconds_local + a.sum_driver_order_time_seconds_local)              AS eoh_sec,
  SUM(a.sum_driver_order_time_seconds_local)                                                               AS order_sec,

  -- Components for rate metrics
  SUM(a.count_rides_sessions_converted_to_finished_order_local)                                           AS sess_fo,
  SUM(a.count_rides_sessions_converted_to_order_local)                                                    AS sess_o,
  SUM(a.count_rides_searches_local)                                                                        AS searches,
  SUM(a.rides_search_count_with_supply_available_local)                                                    AS searches_sup,
  SUM(CAST(a.rides_finished_order_ride_distance_km_local                        AS DOUBLE))               AS dist_km,
  SUM(CAST(a.rides_search_sum_selected_surge_multiplier_finished_orders_local   AS DOUBLE))               AS surge_sum,
  SUM(a.sum_rides_finished_order_pickup_ata_minutes_local)                                                 AS ata_sum,
  SUM(a.count_rides_order_try_state_driver_accepted_local)                                                 AS tries_acc,
  SUM(a.count_rides_order_order_tries_local)                                                               AS tries_tot,
  SUM(a.rides_order_tries_nonoptional_created_local)                                                       AS tries_nonopt,

  -- Spend components
  SUM(CAST(a.rides_demand_spend_eur_local                         AS DOUBLE))                             AS dspend_eur,
  SUM(CAST(a.rides_supply_spend_eur_local                         AS DOUBLE))                             AS sspend_eur,
  SUM(CAST(a.rides_supply_spend_branding_bonus_type_eur_local     AS DOUBLE))                             AS bspend_eur,
  SUM(CAST(a.rides_dynamic_commission_adjustment_eur_local        AS DOUBLE))                             AS dcc_eur,

  -- Non-additive metrics: FO-weighted hourly averages
  -- (best approximation for daily city-level aggregation without raw partner/rider tables)
  SUM(CAST(na.rides_net_rate_eur_local                        AS DOUBLE) * a.rides_orders_in_finished_state_local) AS n_wsum,
  SUM(CAST(na.rides_partners_with_orders_finished_local       AS DOUBLE) * a.rides_orders_in_finished_state_local) AS ap_wsum,
  SUM(CAST(na.rides_users_with_orders_finished_local          AS DOUBLE) * a.rides_orders_in_finished_state_local) AS ar_wsum,

  -- Search-radius quality metrics
  -- ar_in_wsum = SUM(rate_inside_SR × tries_inside_SR): weighted accepted count inside SR
  SUM(CAST(na.rides_order_try_nonoptional_acceptance_rate_local AS DOUBLE) * a.rides_order_tries_nonoptional_created_local) AS ar_in_wsum

FROM hive_metastore.mart_models_spark.mart_city_hour_local_rides a
LEFT JOIN hive_metastore.mart_models_spark.mart_non_additive_city_hour_local_rides na
  ON a.city_id        = na.city_id
 AND a.date_hour_ts_local = na.date_hour_ts_local
WHERE a.country_name = 'Spain'
  AND a.calendar_date_local >= '{start_date}'
GROUP BY CAST(a.calendar_date_local AS STRING), a.city_name
ORDER BY d, c
""".strip()


def _safe(v):
    """Return float or None."""
    try:
        f = float(v)
        return None if (f != f) else f   # NaN check
    except (TypeError, ValueError):
        return None


def load_data():
    from databricks import sql as dbsql

    conn = dbsql.connect(
        server_hostname = DATABRICKS_HOST,
        http_path       = DATABRICKS_HTTP_PATH,
        access_token    = DATABRICKS_TOKEN,
    )

    query = SQL.format(start_date=START_DATE)
    print(f"Querying Databricks from {START_DATE}…")

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    conn.close()
    print(f"  → {len(rows)} city-day rows returned")

    data = []
    for row in rows:
        r = dict(zip(cols, row))

        f   = _safe(r['f']) or 0
        g   = _safe(r['g']) or 0
        o_s = _safe(r['o_sec']) or 0       # online seconds
        o   = o_s / 3600.0                 # online hours

        sess       = _safe(r['sess'])    or 0
        pa         = _safe(r['pa'])      or 0
        nra        = _safe(r['nra'])     or 0
        orders     = _safe(r['orders'])  or 0
        paid_sec   = _safe(r['paid_sec']) or 0
        eoh_sec    = _safe(r['eoh_sec']) or 0
        order_sec  = _safe(r['order_sec']) or 0
        paid       = paid_sec / 3600.0
        eoh        = eoh_sec / 3600.0

        sess_fo    = _safe(r['sess_fo'])
        sess_o     = _safe(r['sess_o'])
        searches   = _safe(r['searches'])
        srch_sup   = _safe(r['searches_sup'])
        dist_km    = _safe(r['dist_km'])
        surge_sum  = _safe(r['surge_sum'])
        ata_sum    = _safe(r['ata_sum'])
        tries_acc  = _safe(r['tries_acc'])
        tries_tot  = _safe(r['tries_tot'])
        tries_nonopt = _safe(r['tries_nonopt'])
        dspend_eur = _safe(r['dspend_eur'])
        sspend_eur = _safe(r['sspend_eur'])
        bspend_eur = _safe(r['bspend_eur'])
        dcc_eur    = _safe(r['dcc_eur'])

        n_ws      = _safe(r['n_wsum'])
        ap_ws     = _safe(r['ap_wsum'])
        ar_ws     = _safe(r['ar_wsum'])
        ar_in_wsum= _safe(r['ar_in_wsum'])

        # Derived rates
        s2f  = (sess_fo / sess * 100)    if sess  and sess_fo  is not None else None
        s2o  = (sess_o  / sess * 100)    if sess  and sess_o   is not None else None
        sc   = (srch_sup / searches * 100) if searches and srch_sup is not None else None
        arp  = (g / f)                   if f else None
        dist = (dist_km / f)             if f and dist_km is not None else None
        ppk  = (g / dist_km)             if dist_km else None
        surge= (surge_sum / f)           if f and surge_sum is not None else None
        ata  = (ata_sum / f)             if f and ata_sum  is not None else None
        oar  = (tries_acc / tries_tot * 100) if tries_tot and tries_acc is not None else None
        o2f  = (f / orders * 100)        if orders else None
        oot  = ((tries_tot - (tries_nonopt or 0)) / tries_tot * 100) if tries_tot else None

        # Search-radius quality metrics
        # oot_gs = same as oot: % of order tries outside search radius
        oot_gs = oot
        # ar_in: acceptance rate inside SR (rate stored as decimal 0-1 in mart)
        ar_in  = (ar_in_wsum / tries_nonopt * 100) \
                 if tries_nonopt and ar_in_wsum is not None else None
        # ar_out: derived — accepted_outside = total_accepted - accepted_inside
        tries_opt = (tries_tot or 0) - (tries_nonopt or 0)
        ar_out = ((tries_acc - ar_in_wsum) / tries_opt * 100) \
                 if tries_opt and tries_acc is not None and ar_in_wsum is not None else None
        util = (order_sec / o_s * 100)   if o_s else None
        paid_util = (paid_sec / o_s * 100) if o_s else None
        eutil= (eoh_sec / o_s * 100)     if o_s else None
        rph  = (f / o)                   if o else None

        # Spend rates (% of GMV)
        dspend   = (dspend_eur / g * 100)              if g and dspend_eur is not None else None
        sspend   = (sspend_eur / g * 100)              if g and sspend_eur is not None else None
        bspend   = (bspend_eur / g * 100)              if g and bspend_eur is not None else None
        dcc      = (dcc_eur    / g * 100)              if g and dcc_eur    is not None else None
        sspend_ex= ((sspend_eur - (bspend_eur or 0)) / g * 100) if g and sspend_eur is not None else None

        # Non-additive FO-weighted averages
        n  = (n_ws  / f * 100) if f and n_ws  is not None else None  # net rate %
        ap = (ap_ws / f)       if f and ap_ws is not None else None  # active partners
        ar = (ar_ws / f)       if f and ar_ws is not None else None  # active riders

        # Further derived from ap/ar
        hpad = (o / ap)   if ap else None
        rpr  = (f / ar)   if ar else None
        # EPH = GMV / Online Hours
        eph  = (g / o) if o else None

        # Skip rows with no meaningful data
        if f == 0 and g == 0:
            continue

        data.append({
            'd': r['d'], 'c': r['c'],
            'f': f, 'g': g, 'n': n, 'o': o,
            'ap': ap, 'pa': pa,
            'eph': eph, 'rph': rph, 'hpad': hpad, 'util': util,
            'ar': ar,
            'sc': sc, 'sess': sess,
            's2f': s2f, 's2o': s2o,
            'arp': arp, 'dist': dist, 'ppk': ppk,
            'surge': surge, 'ata': ata,
            'orders': orders,
            'oar': oar,
            'paid': paid, 'paid_util': paid_util,
            'eoh': eoh, 'eutil': eutil,
            'eph_b': None,   # not derivable from mart tables
            'par': None,     # not derivable from mart tables
            'o2f': o2f, 'rpr': rpr,
            'dspend': dspend, 'sspend': sspend,
            'bspend': bspend, 'dcc': dcc, 'sspend_ex': sspend_ex,
            'nra': nra, 'oot': oot,
            'oot_gs': oot_gs, 'ar_in': ar_in, 'ar_out': ar_out,
        })

    return data
