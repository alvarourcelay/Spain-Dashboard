#!/usr/bin/env python3
"""Generate Bolt City Performance Dashboard — v6
Data source: Databricks (DATA_SOURCE=databricks) or CSV (default).
"""

import csv, json, os
from datetime import datetime, timedelta
from pricing_loader import load_pricing_data
from quality_loader import load_quality_data

LAUNCH_DATES = {
    'A Coruña':  '2025-09-24', 'Alicante':  '2026-02-27',
    'Barcelona': '2025-01-01', 'Madrid':    '2025-01-01',
    'Malaga':    '2025-01-01', 'Murcia':    '2025-07-16',
    'Pamplona':  '2025-10-29', 'Sevilla':   '2025-01-01',
    'Toledo':    '2025-08-28', 'Valencia':  '2026-02-26',
    'Zaragoza':  '2025-03-12',
}
EXPANSION_EXCLUDE = {'Sevilla','Barcelona','Madrid','Malaga'}
ROS_EXCLUDE       = {'Madrid'}

DATA_SOURCE = os.environ.get('DATA_SOURCE', 'csv')

# ── Databricks mode ──────────────────────────────────────────────────────────
if DATA_SOURCE == 'databricks':
    from databricks_loader import load_data
    data = load_data()

# ── CSV mode (local / fallback) ───────────────────────────────────────────────
else:
    def clean_num(s):
        if not s: return None
        s = str(s).strip().replace('€','').replace('%','').replace(',','')
        try: return float(s)
        except: return None

    CSV_PATH = os.environ.get(
        'CSV_PATH',
        '/sessions/busy-eager-einstein/mnt/uploads/cross_domain metrics_by_region__rides 2026-05-04T1001.csv'
    )
    data = []
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            city, date = row['City Name'], row['Date']
            if date < LAUNCH_DATES.get(city, '2099-01-01'): continue
            fo=clean_num(row['Finished orders']); gm=clean_num(row['GMV (EUR)'])
            if fo is None and gm is None: continue
            data.append({'d':date,'c':city,
                'f':fo or 0,'g':gm or 0,'n':clean_num(row['Net Rate %']),'o':clean_num(row['Online (h)']) or 0,
                'ap':clean_num(row['Active Partners']) or 0,
                'pa':clean_num(row['Partner Activations']) or 0,
                'eph':clean_num(row['EPH (without bonuses)']),
                'rph':clean_num(row['RPH']),
                'hpad':clean_num(row['Hours per Active Driver']),
                'util':clean_num(row['Utilisation']),
                'ar':clean_num(row['Active Riders']) or 0,
                'sc':clean_num(row['Search coverage']),
                'sess':clean_num(row['Sessions']) or 0,
                's2f':clean_num(row['S2F %']),'s2o':clean_num(row['S2O %']),
                'arp':clean_num(row['Average Ride Price (EUR)']),
                'dist':clean_num(row['Average Ride Distance for Finished Orders']),
                'ppk':clean_num(row['Price per Km (EUR)']),
                'surge':clean_num(row['Average Selected Surge Multiplier (Local)']),
                'ata':clean_num(row['Average ATA (mins)']),
                'orders':clean_num(row['Orders']) or 0,
                'oar':clean_num(row['Order Acceptance Rate %']),
                'paid':clean_num(row['Paid time (hrs)']) or 0,
                'paid_util':clean_num(row['Paid time utilisation %']),
                'eoh':clean_num(row['Effective Online Hours ']) or 0,
                'eutil':clean_num(row['effective utilisation % ']),
                'eph_b':clean_num(row['EPH (with bonuses)']),
                'par':clean_num(row['Partner Acceptance Rate %']),
                'o2f':clean_num(row['O2F %']),
                'rpr':clean_num(row['Rides per Active Rider (RPR)']),
                'dspend':clean_num(row['Demand Spend %']),
                'sspend':clean_num(row['Supply Spend %']),
                'bspend':clean_num(row['Branding spend %']),
                'dcc':clean_num(row['dynamic commission costs %']),
                'sspend_ex':clean_num(row['Supply spend % (excluding branding spend %)']),
                'nra':clean_num(row['New Rider Activations (works only with city grain)']) or 0,
                'oot':clean_num(row['Optional Order Try %']),
            })

data.sort(key=lambda x:(x['d'],x['c']))

# ── Load pricing data from Google Sheets ─────────────────────────────────────
print('Loading pricing data from Google Sheets…')
pricing_data    = load_pricing_data()
pricing_json    = json.dumps(pricing_data, separators=(',',':'))

# ── Load quality data from Google Sheets ─────────────────────────────────────
print('Loading quality data from Google Sheets…')
quality_raw = load_quality_data()  # {city: {date: {oot_gs, ar_in, ar_out}}}

# Merge quality fields into each data row (left-join on city + date)
for row in data:
    q = quality_raw.get(row['c'], {}).get(row['d'], {})
    row['oot_gs'] = q.get('oot_gs')
    row['ar_in']  = q.get('ar_in')
    row['ar_out'] = q.get('ar_out')
all_cities   = sorted(set(d['c'] for d in data))
min_date     = min(d['d'] for d in data)
max_date     = max(d['d'] for d in data)
default_from = (datetime.strptime(max_date,'%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
expansion_cities = sorted([c for c in all_cities if c not in EXPANSION_EXCLUDE])
ros_cities       = sorted([c for c in all_cities if c not in ROS_EXCLUDE])

palette = ['#2A9C64','#0C2C1C','#52B882','#1B6843','#7DCE9E','#3A8060','#A5E5C0','#0A4228','#68B890','#1E4534','#B0EDD6']
city_colors = {c: palette[i % len(palette)] for i,c in enumerate(all_cities)}

data_json      = json.dumps(data,             separators=(',',':'))
cities_json    = json.dumps(all_cities,       separators=(',',':'))
colors_json    = json.dumps(city_colors,      separators=(',',':'))
expansion_json = json.dumps(expansion_cities, separators=(',',':'))
ros_json       = json.dumps(ros_cities,       separators=(',',':'))

TMPL = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bolt — City Performance</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--g:#2A9C64;--d:#0C2C1C;--w:#fff;--b:#000;--border:#E8E8E8;--t2:#666;--bg:#F2F3F5;--cbg:#FAFAFA}
body{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;background:var(--bg);color:var(--b);font-size:14px}

/* NAV */
nav{background:var(--d);padding:0 28px;height:56px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.nav-logo{font-weight:800;font-size:21px;color:var(--g);letter-spacing:-.5px}
.nav-dot{color:#3a6e52;font-size:18px}
.nav-title{color:#fff;font-weight:500;font-size:15px;opacity:.85}
.nav-badge{margin-left:auto;background:#1a4a30;color:#8de0b6;border-radius:6px;padding:4px 10px;font-size:11px;font-weight:600}

/* LAYOUT */
.main{max-width:1440px;margin:0 auto;padding:20px 24px;display:flex;flex-direction:column;gap:16px}

/* FILTER BAR */
.filter-bar{background:var(--w);border:1px solid var(--border);border-radius:12px;padding:16px 20px;display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start;position:sticky;top:56px;z-index:99;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.filter-group{display:flex;flex-direction:column;gap:8px}
.filter-label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:var(--d)}
.pills{display:flex;flex-wrap:wrap;gap:5px;align-items:center}
.pdivider{width:1px;height:22px;background:var(--border);margin:0 4px}
.pill{padding:5px 13px;border-radius:20px;border:1.5px solid var(--border);background:var(--w);color:var(--b);font-size:12px;font-weight:500;cursor:pointer;transition:all .12s;font-family:inherit;line-height:1.4}
.pill:hover{border-color:var(--g);color:var(--g)}
.pill.active{background:var(--g);border-color:var(--g);color:#fff}
.pill-group{background:var(--d);border-color:var(--d);color:#fff}
.pill-group:hover{background:#1c4a31;border-color:#1c4a31;color:#fff}
.pill-group.active{background:var(--g);border-color:var(--g)}
.pill-all.partial{background:var(--w);border-color:var(--border);color:var(--b)}
.seg{display:flex;border:1.5px solid var(--border);border-radius:8px;overflow:hidden}
.seg-btn{padding:6px 18px;background:var(--w);border:none;font-family:inherit;font-size:13px;font-weight:500;cursor:pointer;color:var(--t2);transition:all .12s}
.seg-btn:not(:last-child){border-right:1.5px solid var(--border)}
.seg-btn.active{background:var(--d);color:#fff}
.date-row{display:flex;gap:8px;align-items:center}
.date-row input{border:1.5px solid var(--border);border-radius:6px;padding:5px 10px;font-family:inherit;font-size:13px;color:var(--b);outline:none;background:var(--w)}
.date-row input:focus{border-color:var(--g)}
.date-sep{color:var(--t2);font-size:13px}

/* KPI CARDS */
.kpi-section{display:flex;flex-direction:column;gap:10px}
.kpi-mode-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.kpi-mode-label{font-size:11px;font-weight:600;color:var(--t2);text-transform:uppercase;letter-spacing:.5px}
.kpi-row{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}
.kpi-card{background:var(--w);border:1px solid var(--border);border-radius:12px;padding:20px 22px;border-top:3px solid var(--g)}
.kpi-label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:var(--t2);margin-bottom:10px}
.kpi-val{font-size:28px;font-weight:800;color:var(--d);line-height:1;letter-spacing:-.5px}
.kpi-period{font-size:11px;color:var(--t2);margin-top:5px;font-weight:500}
.kpi-sub{margin-top:6px;font-size:12px;font-weight:500}
.kpi-up{color:var(--g)} .kpi-dn{color:#999}

/* METRIC SECTIONS */
.sec-section{background:var(--w);border:1px solid var(--border);border-radius:12px;padding:18px 20px}
.sec-hdr{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:var(--d);margin-bottom:14px;display:flex;align-items:center;gap:10px}
.sec-hdr::after{content:'';flex:1;height:1px;background:var(--border)}
.sec-grid{display:grid;gap:8px}
.sec-grid-6{grid-template-columns:repeat(6,1fr)}
.sec-grid-5{grid-template-columns:repeat(5,1fr)}
.sec-grid-3{grid-template-columns:repeat(3,1fr)}
.sec-grid-4{grid-template-columns:repeat(4,1fr)}
.sc-card{padding:12px 14px;border:1px solid var(--border);border-radius:8px;border-top:2px solid var(--g);background:var(--cbg)}
.sc-label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--t2);margin-bottom:5px}
.sc-val{font-size:19px;font-weight:700;color:var(--d);line-height:1.2;letter-spacing:-.3px}
.sc-chg{font-size:11px;font-weight:500;margin-top:4px}

/* SECTION CHART */
.sec-chart{margin-top:18px;border-top:1px solid var(--border);padding-top:16px}
.sec-chart-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:8px}
.sec-chart-title{font-size:13px;font-weight:600;color:var(--d)}
.sec-chart-note{font-size:11px;color:var(--t2);margin-top:2px}
.sec-chart-body{position:relative;height:260px}

/* METRIC CHECK PILLS (shared by main chart and section charts) */
.metric-checks{display:flex;gap:5px;flex-wrap:wrap}
.mcheck{padding:4px 12px;border-radius:20px;border:1.5px solid var(--border);background:var(--w);color:var(--t2);font-family:inherit;font-size:11px;font-weight:500;cursor:pointer;transition:all .12s;display:flex;align-items:center;gap:4px}
.mcheck:hover{border-color:var(--g);color:var(--g)}
.mcheck.active{background:var(--g);border-color:var(--g);color:#fff}
.mcheck-bar{background:var(--d);border-color:var(--d);color:#fff}
.mcheck-bar:hover{background:#1c4a31;border-color:#1c4a31;color:#fff}
.mcheck-bar.active{background:var(--g);border-color:var(--g)}
.mcheck-tick{font-size:10px;opacity:.7}

/* MAIN CHART */
.chart-card{background:var(--w);border:1px solid var(--border);border-radius:12px;padding:22px 24px}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px}
.card-title{font-size:15px;font-weight:600;color:var(--d)}
.chart-note{font-size:11px;color:var(--t2);margin-top:4px}
.chart-wrap{position:relative;height:360px}

/* TABLE */
.table-card{background:var(--w);border:1px solid var(--border);border-radius:12px;padding:22px 24px}
.tbl-scroll{overflow-x:auto;margin-top:4px}
table{width:100%;border-collapse:collapse}
thead th{background:var(--d);color:#fff;font-weight:600;font-size:12px;padding:12px 16px;text-align:left;white-space:nowrap;cursor:pointer;user-select:none;letter-spacing:.2px}
thead th:first-child{border-radius:6px 0 0 0} thead th:last-child{border-radius:0 6px 0 0}
thead th:hover{background:#1c4a31} thead th.th-sorted{background:var(--g)}
.sort-arrow{margin-left:4px;opacity:.7;font-size:10px}
tbody tr:nth-child(even){background:#FAFAFA} tbody tr:hover{background:#F0FAF4}
tbody td{padding:12px 16px;font-size:13px;border-bottom:1px solid var(--border);white-space:nowrap}
tbody td:first-child{font-weight:600;color:var(--d)}
.best-badge{background:var(--g);color:#fff;border-radius:4px;padding:1px 7px;font-size:10px;font-weight:700;margin-left:6px;vertical-align:middle}
.city-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle}

/* HISTORICAL TABLE */
.hist-card{background:var(--w);border:1px solid var(--border);border-radius:12px;padding:22px 24px}
.hist-scroll{overflow:auto;max-height:620px;margin-top:4px;border-radius:8px;border:1px solid var(--border)}
.hist-tbl thead{position:sticky;top:0;z-index:5}
.hist-tbl{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}
.hist-tbl thead th{padding:8px 10px;font-size:11px;font-weight:600;text-align:center;border-bottom:1px solid var(--border);border-right:1px solid rgba(255,255,255,.15)}
.hist-tbl thead .sec-hdr-main{background:var(--d);color:#fff}
.hist-tbl thead .sec-hdr-supply{background:#1B5E3A;color:#fff}
.hist-tbl thead .sec-hdr-demand{background:#1B4A31;color:#fff}
.hist-tbl thead .sec-hdr-pricing{background:#2A3F32;color:#fff}
.hist-tbl thead .sec-hdr-quality{background:#0A3D22;color:#fff}
.hist-tbl thead .metric-hdr{background:#f7f7f7;color:var(--d);font-size:10px;letter-spacing:.3px;border-top:none;border-right:1px solid var(--border)}
.hist-tbl thead .period-hdr{background:var(--d);color:#fff;text-align:left;border-right:2px solid #2A9C64;min-width:90px}
.hist-tbl tbody tr:nth-child(odd){background:#FAFAFA}
.hist-tbl tbody tr:hover{background:#F0FAF4}
.hist-tbl tbody td{padding:7px 10px;border-bottom:1px solid var(--border);vertical-align:middle;text-align:right}
.hist-tbl tbody td.hist-day{text-align:center;font-weight:500;color:#888;font-size:11px;width:36px;min-width:36px;position:sticky;left:0;background:inherit;z-index:1;border-right:none;padding:7px 6px}
.hist-tbl tbody td.hist-period{text-align:left;font-weight:600;color:var(--d);border-right:2px solid #e0e0e0;font-size:12px;min-width:90px;position:sticky;left:36px;background:inherit;z-index:1}
.hist-tbl tbody tr:nth-child(odd) td.hist-day,.hist-tbl tbody tr:nth-child(odd) td.hist-period{background:#FAFAFA}
.hist-tbl tbody tr:hover td.hist-day,.hist-tbl tbody tr:hover td.hist-period{background:#F0FAF4}
.hist-tbl tbody tr.hist-prev-hl{background:#E8F5E9!important}
.hist-tbl tbody tr.hist-prev-hl td.hist-day,.hist-tbl tbody tr.hist-prev-hl td.hist-period{background:#E8F5E9!important}
.hist-tbl tbody td.hist-val{font-size:12px;color:var(--d);font-weight:500;padding-right:4px;border-right:none}
.hist-tbl tbody td.hist-chg{font-size:11px;font-weight:600;padding-left:3px;border-right:2px solid #c8d8cc}
.hist-tbl .chg-pos{color:#2A9C64}.hist-tbl .chg-neg{color:#c0392b}.hist-tbl .chg-nil{color:#aaa}

@media(max-width:1200px){.sec-grid-6{grid-template-columns:repeat(3,1fr)}.sec-grid-5{grid-template-columns:repeat(3,1fr)}}
@media(max-width:1000px){.kpi-row{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.kpi-row{grid-template-columns:1fr}.sec-grid-6,.sec-grid-5,.sec-grid-3{grid-template-columns:repeat(2,1fr)}}

/* PRICING SECTION */
.pricing-controls{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap;margin-bottom:20px}
.pricing-select{border:1.5px solid var(--border);border-radius:7px;padding:6px 28px 6px 10px;font-family:inherit;font-size:13px;font-weight:500;background:var(--w);cursor:pointer;min-width:140px;color:var(--b)}
.pricing-select:focus{outline:none;border-color:var(--g)}
.pricing-flabel{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--d);margin-bottom:5px}
.pgap-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}
@media(max-width:700px){.pgap-grid{grid-template-columns:1fr}}
.pgap-card{background:var(--cbg);border:1px solid var(--border);border-radius:10px;padding:16px 18px}
.pgap-card-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--d);margin-bottom:14px}
.pgap-chart-wrap{position:relative;height:220px}
.pricing-empty{padding:40px;text-align:center;color:#999;font-style:italic}
.pgap-legend{display:flex;gap:14px;margin-top:10px;flex-wrap:wrap;font-size:11px;color:var(--muted);align-items:center}
.pgap-legend-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--t2)}
.pgap-legend-dot{width:10px;height:10px;border-radius:2px}
.pgap-dot{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}
.pgap-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:12px}
</style>
</head>
<body>
<nav>
  <span class="nav-logo">Bolt</span><span class="nav-dot">·</span>
  <span class="nav-title">City Performance Dashboard</span>
  <span class="nav-badge" id="nav-badge">Loading…</span>
</nav>
<div class="main">

  <!-- FILTERS -->
  <div class="filter-bar">
    <div class="filter-group">
      <span class="filter-label">Cities</span>
      <div class="pills" id="city-pills"></div>
    </div>
    <div class="filter-group">
      <span class="filter-label">Granularity</span>
      <div class="seg">
        <button class="seg-btn"        data-g="daily"   onclick="setGran(this)">Daily</button>
        <button class="seg-btn active" data-g="weekly"  onclick="setGran(this)">Weekly</button>
        <button class="seg-btn"        data-g="monthly" onclick="setGran(this)">Monthly</button>
      </div>
    </div>
    <div class="filter-group">
      <span class="filter-label">Date range</span>
      <div class="date-row">
        <input type="date" id="df" value="__DEFAULT_FROM__" min="__MIN_DATE__" max="__MAX_DATE__" onchange="onDate()">
        <span class="date-sep">→</span>
        <input type="date" id="dt" value="__MAX_DATE__" min="__MIN_DATE__" max="__MAX_DATE__" onchange="onDate()">
      </div>
    </div>
  </div>

  <!-- MARKETPLACE KPI CARDS + CHART -->
  <div class="kpi-section">
    <div class="kpi-mode-row">
      <div id="kpi-mode-grp" style="display:flex;align-items:center;gap:12px">
        <span class="kpi-mode-label">KPI cards show</span>
        <div class="seg">
          <button class="seg-btn active" data-km="range" onclick="setKpiMode(this)">Full range</button>
          <button class="seg-btn"        data-km="prev"  onclick="setKpiMode(this)">Previous period</button>
        </div>
      </div>
      <div style="margin-left:auto;display:flex;align-items:center;gap:10px">
        <span class="kpi-mode-label">Additional views</span>
        <div class="seg">
          <button class="seg-btn" id="yoy-btn" onclick="toggleYoY()">Year over Year</button>
        </div>
      </div>
    </div>
    <div class="kpi-row" id="kpi-row"></div>
  </div>

  <!-- MAIN CHART -->
  <div class="chart-card">
    <div class="card-header">
      <div><div class="card-title">Marketplace</div><div class="chart-note" id="chart-note"></div></div>
      <div class="metric-checks">
        <button class="mcheck active"     data-m="f" onclick="toggleMetric(this)"><span class="mcheck-tick">✓</span> Finished Orders</button>
        <button class="mcheck"            data-m="g" onclick="toggleMetric(this)"><span class="mcheck-tick">✓</span> GMV</button>
        <button class="mcheck mcheck-bar" data-m="n"    onclick="toggleMetric(this)"><span class="mcheck-tick">✓</span> Net Rate % ▐</button>
        <button class="mcheck"            data-m="o"    onclick="toggleMetric(this)"><span class="mcheck-tick">✓</span> Online Hours</button>
        <button class="mcheck"            data-m="sess" onclick="toggleMetric(this)"><span class="mcheck-tick">✓</span> Sessions</button>
      </div>
    </div>
    <div class="chart-wrap"><canvas id="chart"></canvas></div>
  </div>

  <!-- SUPPLY -->
  <div class="sec-section">
    <div class="sec-hdr">Supply</div>
    <div class="sec-grid sec-grid-6" id="supply-cards"></div>
    <div class="sec-chart">
      <div class="sec-chart-head">
        <div><div class="sec-chart-title">Trend</div><div class="sec-chart-note" id="supply-note"></div></div>
        <div class="metric-checks" id="supply-pills"></div>
      </div>
      <div class="sec-chart-body"><canvas id="supply-chart"></canvas></div>
    </div>
  </div>

  <!-- DEMAND -->
  <div class="sec-section">
    <div class="sec-hdr">Demand</div>
    <div class="sec-grid sec-grid-5" id="demand-cards"></div>
    <div class="sec-chart">
      <div class="sec-chart-head">
        <div><div class="sec-chart-title">Trend</div><div class="sec-chart-note" id="demand-note"></div></div>
        <div class="metric-checks" id="demand-pills"></div>
      </div>
      <div class="sec-chart-body"><canvas id="demand-chart"></canvas></div>
    </div>
  </div>

  <!-- PRICING -->
  <div class="sec-section">
    <div class="sec-hdr">Pricing</div>
    <div class="sec-grid sec-grid-5" id="pricing-cards"></div>
    <div class="sec-chart">
      <div class="sec-chart-head">
        <div><div class="sec-chart-title">Trend</div><div class="sec-chart-note" id="pricing-note"></div></div>
        <div class="metric-checks" id="pricing-pills"></div>
      </div>
      <div class="sec-chart-body"><canvas id="pricing-chart"></canvas></div>
    </div>
  </div>

  <!-- PRICING COMPETITIVENESS -->
  <div class="chart-card" id="pricing-section">
    <div class="card-header">
      <div>
        <div class="card-title">⚡ Pricing Gap vs Competitors — Performance by Region</div>
        <div class="chart-note">Positive = Bolt more expensive · Negative = Bolt cheaper · Surge included</div>
      </div>
    </div>
    <div class="pricing-controls">
      <div>
        <div class="pricing-flabel">CITY</div>
        <select class="pricing-select" id="p-city" onchange="onPCity()"></select>
      </div>
      <div>
        <div class="pricing-flabel">REGION</div>
        <select class="pricing-select" id="p-region" onchange="renderPricing()"></select>
      </div>
    </div>
    <div id="pricing-body"></div>
  </div>

  <!-- QUALITY -->
  <div class="sec-section">
    <div class="sec-hdr">Quality</div>
    <div class="sec-grid sec-grid-6" id="quality-cards"></div>
    <div class="sec-chart">
      <div class="sec-chart-head">
        <div><div class="sec-chart-title">Trend</div><div class="sec-chart-note" id="quality-note"></div></div>
        <div class="metric-checks" id="quality-pills"></div>
      </div>
      <div class="sec-chart-body"><canvas id="quality-chart"></canvas></div>
    </div>
  </div>

  <!-- GENERAL DASHBOARD -->
  <div class="sec-section">
    <div class="sec-hdr">General Dashboard</div>
    <div class="sec-chart" style="border-top:none;padding-top:0;margin-top:0">
      <div class="sec-chart-head">
        <div><div class="sec-chart-title">Select metrics from any section to compare</div><div class="sec-chart-note" id="general-note"></div></div>
        <div class="metric-checks" id="general-pills" style="flex-wrap:wrap;max-width:900px"></div>
      </div>
      <div class="sec-chart-body" style="height:340px"><canvas id="general-chart"></canvas></div>
    </div>
  </div>

  <!-- HISTORICAL PERFORMANCE TABLE -->
  <div class="hist-card">
    <div class="card-header">
      <div><div class="card-title">Historical Performance</div><div class="chart-note" id="hist-note"></div></div>
    </div>
    <div class="hist-scroll"><table class="hist-tbl" id="hist-tbl"></table></div>
  </div>


</div>
<script>
// ── DATA ──────────────────────────────────────────────────────────────
const DATA        = __DATA__;
const ALL_CITIES  = __CITIES__;
const CITY_COLORS = __COLORS__;
const EXPANSION   = __EXPANSION__;
const ROS         = __ROS__;
const PRICING_DATA = __PRICING_DATA__;
const DATA_MIN    = '__MIN_DATE__';
const DATA_MAX    = '__MAX_DATE__';

// ── SECTION CONFIGS ───────────────────────────────────────────────────
// bar:true  → plotted as bars on right Y-axis (% metrics)
// bar:false → plotted as lines on left Y-axis
const SECTIONS = {
  supply: {
    metrics: [
      {k:'o',   label:'Online Hours',        bar:false},
      {k:'pa',  label:'Partner Activations', bar:false},
      {k:'eph', label:'EPH',                 bar:false},
      {k:'rph', label:'RPH',                 bar:false},
      {k:'hpad',label:'Hrs / Driver',        bar:false},
      {k:'util',label:'Utilisation',         bar:true },
    ],
    default:['eph'],
    inst: null,
  },
  demand: {
    metrics: [
      {k:'ar',  label:'Active Riders',     bar:false},
      {k:'sess',label:'Sessions',          bar:false},
      {k:'sc',  label:'Search Coverage',  bar:true },
      {k:'s2f', label:'S2F %',            bar:true },
      {k:'s2o', label:'S2O %',            bar:true },
    ],
    default:['sess'],
    inst: null,
  },
  pricing: {
    metrics: [
      {k:'arp',  label:'Avg Ride Price', bar:false},
      {k:'dist', label:'Avg Distance',   bar:false},
      {k:'ppk',  label:'Price / km',     bar:false},
      {k:'surge',label:'Surge',          bar:false},
      {k:'ata',  label:'ATA (mins)',      bar:false},
    ],
    default:['arp'],
    inst: null,
  },
  quality: {
    metrics: [
      {k:'o2f',    label:'O2F %',              bar:false},
      {k:'oar',    label:'Order Accept. Rate', bar:false},
      {k:'par',    label:'Partner Accept.',    bar:false},
      {k:'oot_gs', label:'% Outside Radius',   bar:false},
      {k:'ar_in',  label:'AR Inside Radius',   bar:false},
      {k:'ar_out', label:'AR Outside Radius',  bar:false},
    ],
    default:['o2f'],
    inst: null,
  },
  general: {
    metrics: [
      // Marketplace
      {k:'f',        label:'Finished Orders',      bar:false},
      {k:'orders',   label:'Orders',               bar:false},
      {k:'g',        label:'GMV',                  bar:false},
      {k:'n',        label:'Net Rate %',            bar:true },
      {k:'o',        label:'Online Hours',          bar:false},
      {k:'sess',     label:'Sessions',              bar:false},
      // Supply
      {k:'ap',       label:'Active Partners',       bar:false},
      {k:'pa',       label:'Partner Act.',          bar:false},
      {k:'nra',      label:'New Rider Act.',        bar:false},
      {k:'eph',      label:'EPH',                   bar:false},
      {k:'eph_b',    label:'EPH (w/ bonuses)',       bar:false},
      {k:'rph',      label:'RPH',                   bar:false},
      {k:'hpad',     label:'Hrs / Driver',           bar:false},
      {k:'paid',     label:'Paid Time (h)',          bar:false},
      {k:'eoh',      label:'Effective OH',           bar:false},
      {k:'util',     label:'Utilisation',            bar:true },
      {k:'paid_util',label:'Paid Utilisation',       bar:true },
      {k:'eutil',    label:'Eff. Utilisation',       bar:true },
      {k:'oar',      label:'Order Accept. Rate',     bar:true },
      {k:'par',      label:'Partner Accept. Rate',   bar:true },
      // Quality (Google Sheet)
      {k:'oot_gs',   label:'% Outside SR',            bar:true },
      {k:'ar_in',    label:'AR Inside SR',             bar:true },
      {k:'ar_out',   label:'AR Outside SR',            bar:true },
      // Demand
      {k:'ar',       label:'Active Riders',          bar:false},
      {k:'rpr',      label:'Rides / Active Rider',   bar:false},
      {k:'sc',       label:'Search Coverage',        bar:true },
      {k:'s2f',      label:'S2F %',                  bar:true },
      {k:'s2o',      label:'S2O %',                  bar:true },
      {k:'o2f',      label:'O2F %',                  bar:true },
      {k:'oot',      label:'Opt. Order Try %',        bar:true },
      // Pricing
      {k:'arp',      label:'Avg Ride Price',          bar:false},
      {k:'dist',     label:'Avg Distance',            bar:false},
      {k:'ppk',      label:'Price / km',              bar:false},
      {k:'surge',    label:'Surge',                   bar:false},
      {k:'ata',      label:'ATA (mins)',               bar:false},
      {k:'dspend',   label:'Demand Spend %',           bar:true },
      {k:'sspend',   label:'Supply Spend %',           bar:true },
      {k:'bspend',   label:'Branding Spend %',         bar:true },
      {k:'dcc',      label:'Dyn. Commission %',        bar:true },
      {k:'sspend_ex',label:'Supply Spend % (ex.brand)',bar:true },
    ],
    default:['f'],
    inst: null,
  },
};
// Section metric selections (mutable)
const SEC_SEL = { supply:['eph'], demand:['sess'], pricing:['arp'], quality:['o2f'], general:['f'] };
// Multi-metric color palette — diverse colors for visual differentiation
const SEC_COLORS=['#2A9C64','#F5B800','#3B82F6','#F97316','#A855F7','#EF4444','#06B6D4','#84CC16','#EC4899','#0EA5E9'];
// Dash patterns for additional differentiation
const SEC_DASHES=[[],[6,3],[2,3],[10,3,2,3],[5,2,2,2]];

// ── GLOBAL STATE ──────────────────────────────────────────────────────
const S = {
  cities: [...ALL_CITIES], gran:'weekly',
  df: document.getElementById('df').value, dt: document.getElementById('dt').value,
  kpiMode:'range', metrics:['f']
};

// ── ROCKET CHART PLUGIN ───────────────────────────────────────────────
Chart.register({id:'rocketATH',afterDatasetsDraw(chart){
  const ctx=chart.ctx;
  chart.data.datasets.forEach((ds,di)=>{
    if(!ds._athFlags)return;
    const meta=chart.getDatasetMeta(di);if(meta.hidden)return;
    ctx.save();ctx.font='13px serif';ctx.textAlign='center';ctx.textBaseline='bottom';
    ds._athFlags.forEach((flag,j)=>{
      if(!flag)return;
      const pt=meta.data[j];if(pt)ctx.fillText(ROCKET,pt.x,pt.y-4);
    });
    ctx.restore();
  });
}});

// ── DATE UTILS ────────────────────────────────────────────────────────
// Always format using LOCAL date components — toISOString() gives UTC
// which shifts the date by 1 day in UTC+1/UTC+2 timezones (e.g. Spain)
function fmtDate(d){
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}
function isoWeek(ds){
  const d=new Date(ds+'T00:00:00');
  const day=d.getDay()||7;            // Mon=1 … Sun=7
  d.setDate(d.getDate()+4-day);       // shift to Thursday of this week
  const yearStart=new Date(d.getFullYear(),0,1);
  const wk=Math.ceil(((d-yearStart)/86400000+1)/7);
  return d.getFullYear()+'-W'+String(wk).padStart(2,'0');
}
function periodKey(ds,gran){if(gran==='daily')return ds;if(gran==='weekly')return isoWeek(ds);return ds.slice(0,7);}
// X-axis labels: for weekly, return [weekLabel, mondayDate] so Chart.js shows 2 lines
function weekToMonday(pk){
  const[y,w]=pk.split('-W').map(Number);
  const jan4=new Date(y,0,4);const dow=jan4.getDay()||7;
  const mon1=new Date(jan4);mon1.setDate(jan4.getDate()-(dow-1));
  const monW=new Date(mon1);monW.setDate(mon1.getDate()+(w-1)*7);return monW;
}
function chartLabels(periods){
  if(S.gran!=='weekly')return periods.map(p=>periodLabel(p,S.gran));
  return periods.map(pk=>{
    const[y,w]=pk.split('-W');
    const mon=weekToMonday(pk);
    const dd=String(mon.getDate()).padStart(2,'0');
    const mm=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][mon.getMonth()];
    return['W'+w.padStart(2,'0')+' \''+y.slice(2), dd+' '+mm];
  });
}
function periodLabel(k,gran){
  if(gran==='daily'){const[y,m,d]=k.split('-');return d+'/'+m+'/'+y.slice(2);}
  if(gran==='weekly'){const[y,w]=k.split('-W');return'W'+w+' \''+y.slice(2);}
  const[y,m]=k.split('-');
  return['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+m-1]+' \''+y.slice(2);
}
function lastCompletePeriod(gran){
  const d=new Date(DATA_MAX+'T00:00:00');
  if(gran==='daily')return{from:DATA_MAX,to:DATA_MAX,label:DATA_MAX};
  if(gran==='weekly'){
    const dow=(d.getDay()+6)%7;
    const prevSun=new Date(d);prevSun.setDate(d.getDate()-dow-1);
    if(fmtDate(prevSun)<DATA_MIN)return null;
    const prevMon=new Date(prevSun);prevMon.setDate(prevSun.getDate()-6);
    const f=fmtDate(prevMon),t=fmtDate(prevSun);
    return{from:f,to:t,label:isoWeek(f)};
  }
  const y=d.getFullYear(),m=d.getMonth(),ld=new Date(y,m+1,0).getDate();
  let py,pm;
  if(d.getDate()===ld){py=y;pm=m;}else{pm=m-1;py=pm<0?y-1:y;pm=pm<0?11:pm;}
  const pld=new Date(py,pm+1,0).getDate(),ms=String(pm+1).padStart(2,'0');
  return{from:`${py}-${ms}-01`,to:`${py}-${ms}-${pld}`,label:`${py}-${ms}`};
}
function prevBeforeLast(gran){
  const last=lastCompletePeriod(gran);if(!last)return null;
  const d=new Date(last.from+'T00:00:00');d.setDate(d.getDate()-1);
  const pt=fmtDate(d);
  if(gran==='daily')return{from:pt,to:pt};
  if(gran==='weekly'){const m=new Date(d);m.setDate(d.getDate()-6);return{from:fmtDate(m),to:pt};}
  const y=d.getFullYear(),m=d.getMonth(),ms=String(m+1).padStart(2,'0');
  return{from:`${y}-${ms}-01`,to:pt};
}
// Last complete period ending on or before toDate (respects user-selected date range)
function lastPeriodInRange(gran,toDate){
  const d=new Date(toDate+'T00:00:00');
  if(gran==='daily')return{from:toDate,to:toDate,label:toDate};
  if(gran==='weekly'){
    const dow=(d.getDay()+6)%7; // 0=Mon … 6=Sun
    const weekEnd=new Date(d);
    weekEnd.setDate(d.getDate()-(dow===6?0:dow+1)); // Sun on or before toDate
    if(fmtDate(weekEnd)<DATA_MIN)return null;
    const weekStart=new Date(weekEnd);weekStart.setDate(weekEnd.getDate()-6);
    const f=fmtDate(weekStart),t=fmtDate(weekEnd);
    return{from:f,to:t,label:isoWeek(f)};
  }
  const y=d.getFullYear(),m=d.getMonth(),ld=new Date(y,m+1,0).getDate();
  let py,pm;
  if(d.getDate()===ld){py=y;pm=m;}else{pm=m-1;py=pm<0?y-1:y;pm=pm<0?11:pm;}
  const pld=new Date(py,pm+1,0).getDate(),ms=String(pm+1).padStart(2,'0');
  return{from:`${py}-${ms}-01`,to:`${py}-${ms}-${pld}`,label:`${py}-${ms}`};
}
function prevBeforeRange(gran,toDate){
  const last=lastPeriodInRange(gran,toDate);if(!last)return null;
  const d=new Date(last.from+'T00:00:00');d.setDate(d.getDate()-1);
  const pt=fmtDate(d);
  if(gran==='daily')return{from:pt,to:pt};
  if(gran==='weekly'){const m=new Date(d);m.setDate(d.getDate()-6);return{from:fmtDate(m),to:pt};}
  const y=d.getFullYear(),m=d.getMonth(),ms=String(m+1).padStart(2,'0');
  return{from:`${y}-${ms}-01`,to:pt};
}

// ── AGGREGATION ───────────────────────────────────────────────────────
function filteredRows(fromD,toD){
  const f=fromD||S.df,t=toD||S.dt;
  return DATA.filter(r=>S.cities.includes(r.c)&&r.d>=f&&r.d<=t);
}
function aggregate(rows){
  const map=new Map();
  for(const r of rows){
    const pk=periodKey(r.d,S.gran);
    if(!map.has(pk))map.set(pk,new Map());
    const cm=map.get(pk);
    if(!cm.has(r.c))cm.set(r.c,{f:0,g:0,ns:0,nw:0,o:0,ap:0,pa:0,ar:0,sess:0,
      orders:0,paid:0,eoh:0,nra:0,
      eph_s:0,rph_s:0,util_s:0,hpad_s:0,eph_b_s:0,paid_util_s:0,eutil_s:0,
      sc_s:0,s2f_s:0,s2o_s:0,o2f_s:0,oot_s:0,
      arp_s:0,dist_s:0,ppk_s:0,surge_s:0,ata_s:0,oar_s:0,par_s:0,rpr_s:0,
      dspend_s:0,dspend_w:0,sspend_s:0,sspend_w:0,bspend_s:0,bspend_w:0,
      dcc_s:0,dcc_w:0,sspend_ex_s:0,sspend_ex_w:0,
      oot_gs_s:0,oot_gs_w:0,ar_in_s:0,ar_in_w:0,ar_out_s:0,ar_out_w:0});
    const a=cm.get(r.c);
    a.f+=r.f;a.g+=r.g;a.o+=r.o;
    if(r.n!=null&&r.g>0){a.ns+=r.n*r.g;a.nw+=r.g;}
    a.ap+=r.ap||0;a.pa+=r.pa||0;a.ar+=r.ar||0;a.sess+=r.sess||0;
    a.orders+=r.orders||0;a.paid+=r.paid||0;a.eoh+=r.eoh||0;a.nra+=r.nra||0;
    const oh=r.o||0,ss=r.sess||0,fo=r.f||0,gv=r.g||0;
    if(oh>0){if(r.eph!=null)a.eph_s+=r.eph*oh;if(r.rph!=null)a.rph_s+=r.rph*oh;
             if(r.util!=null)a.util_s+=r.util*oh;if(r.hpad!=null)a.hpad_s+=r.hpad*oh;
             if(r.eph_b!=null)a.eph_b_s+=r.eph_b*oh;if(r.paid_util!=null)a.paid_util_s+=r.paid_util*oh;
             if(r.eutil!=null)a.eutil_s+=r.eutil*oh;}
    if(ss>0){if(r.sc!=null)a.sc_s+=r.sc*ss;if(r.s2f!=null)a.s2f_s+=r.s2f*ss;if(r.s2o!=null)a.s2o_s+=r.s2o*ss;
             if(r.o2f!=null)a.o2f_s+=r.o2f*ss;if(r.oot!=null)a.oot_s+=r.oot*ss;}
    if(fo>0){if(r.arp!=null)a.arp_s+=r.arp*fo;if(r.dist!=null)a.dist_s+=r.dist*fo;if(r.ppk!=null)a.ppk_s+=r.ppk*fo;
             if(r.surge!=null)a.surge_s+=r.surge*fo;if(r.ata!=null)a.ata_s+=r.ata*fo;
             if(r.oar!=null)a.oar_s+=r.oar*fo;if(r.par!=null)a.par_s+=r.par*fo;if(r.rpr!=null)a.rpr_s+=r.rpr*fo;
             if(r.oot_gs!=null){a.oot_gs_s+=r.oot_gs*fo;a.oot_gs_w+=fo;}
             if(r.ar_in!=null) {a.ar_in_s +=r.ar_in *fo;a.ar_in_w +=fo;}
             if(r.ar_out!=null){a.ar_out_s+=r.ar_out*fo;a.ar_out_w+=fo;}}
    if(gv>0){if(r.dspend!=null){a.dspend_s+=r.dspend*gv;a.dspend_w+=gv;}
             if(r.sspend!=null){a.sspend_s+=r.sspend*gv;a.sspend_w+=gv;}
             if(r.bspend!=null){a.bspend_s+=r.bspend*gv;a.bspend_w+=gv;}
             if(r.dcc!=null){a.dcc_s+=r.dcc*gv;a.dcc_w+=gv;}
             if(r.sspend_ex!=null){a.sspend_ex_s+=r.sspend_ex*gv;a.sspend_ex_w+=gv;}}
  }
  return map;
}

// Extract computed value from an accumulator object for any metric key
function accVal(a,k){
  const v={f:a.f,g:a.g,n:a.nw>0?a.ns/a.nw:null,o:a.o,ap:a.ap,pa:a.pa,ar:a.ar,sess:a.sess,
    orders:a.orders,paid:a.paid,eoh:a.eoh,nra:a.nra,
    eph:a.o>0?a.eph_s/a.o:null,rph:a.o>0?a.rph_s/a.o:null,
    util:a.o>0?a.util_s/a.o:null,hpad:a.o>0?a.hpad_s/a.o:null,
    eph_b:a.o>0?a.eph_b_s/a.o:null,paid_util:a.o>0?a.paid_util_s/a.o:null,
    eutil:a.o>0?a.eutil_s/a.o:null,
    sc:a.sess>0?a.sc_s/a.sess:null,s2f:a.sess>0?a.s2f_s/a.sess:null,s2o:a.sess>0?a.s2o_s/a.sess:null,
    o2f:a.sess>0?a.o2f_s/a.sess:null,oot:a.sess>0?a.oot_s/a.sess:null,
    arp:a.f>0?a.arp_s/a.f:null,dist:a.f>0?a.dist_s/a.f:null,ppk:a.f>0?a.ppk_s/a.f:null,
    surge:a.f>0?a.surge_s/a.f:null,ata:a.f>0?a.ata_s/a.f:null,
    oar:a.f>0?a.oar_s/a.f:null,par:a.f>0?a.par_s/a.f:null,rpr:a.f>0?a.rpr_s/a.f:null,
    dspend:a.dspend_w>0?a.dspend_s/a.dspend_w:null,sspend:a.sspend_w>0?a.sspend_s/a.sspend_w:null,
    bspend:a.bspend_w>0?a.bspend_s/a.bspend_w:null,dcc:a.dcc_w>0?a.dcc_s/a.dcc_w:null,
    sspend_ex:a.sspend_ex_w>0?a.sspend_ex_s/a.sspend_ex_w:null,
    oot_gs:a.oot_gs_w>0?a.oot_gs_s/a.oot_gs_w:null,
    ar_in: a.ar_in_w >0?a.ar_in_s /a.ar_in_w :null,
    ar_out:a.ar_out_w>0?a.ar_out_s/a.ar_out_w:null};
  return v[k]??null;
}
// Aggregate across all selected cities per period, return [{pk, val}]
function aggSum(byP,k){
  return[...byP.keys()].sort().map(pk=>{
    const cm=byP.get(pk);if(!cm)return{pk,val:null};
    const merged={f:0,g:0,ns:0,nw:0,o:0,ap:0,pa:0,ar:0,sess:0,
      orders:0,paid:0,eoh:0,nra:0,
      eph_s:0,rph_s:0,util_s:0,hpad_s:0,eph_b_s:0,paid_util_s:0,eutil_s:0,
      sc_s:0,s2f_s:0,s2o_s:0,o2f_s:0,oot_s:0,
      arp_s:0,dist_s:0,ppk_s:0,surge_s:0,ata_s:0,oar_s:0,par_s:0,rpr_s:0,
      dspend_s:0,dspend_w:0,sspend_s:0,sspend_w:0,bspend_s:0,bspend_w:0,
      dcc_s:0,dcc_w:0,sspend_ex_s:0,sspend_ex_w:0,
      oot_gs_s:0,oot_gs_w:0,ar_in_s:0,ar_in_w:0,ar_out_s:0,ar_out_w:0};
    for(const[,a]of cm)for(const key of Object.keys(merged))merged[key]+=a[key]||0;
    return{pk,val:accVal(merged,k)};
  });
}
// Per-city values per period for one metric key
function aggCity(byP,city,k){
  return[...byP.keys()].sort().map(pk=>{
    const a=byP.get(pk)?.get(city);if(!a)return null;
    return{pk,val:accVal(a,k)};
  }).filter(Boolean);
}
function totals(byP){
  let f=0,g=0,ns=0,nw=0,o=0,sess=0;
  for(const[,cm]of byP)for(const[,a]of cm){f+=a.f;g+=a.g;ns+=a.ns;nw+=a.nw;o+=a.o;sess+=a.sess;}
  return{f,g,n:nw>0?ns/nw:null,o,sess};
}
function secTotals(byP){
  // build merged accumulator from all city/period data
  const st={f:0,g:0,ns:0,nw:0,o:0,ap:0,pa:0,ar:0,sess:0,orders:0,paid:0,eoh:0,nra:0,
    eph_s:0,rph_s:0,util_s:0,hpad_s:0,eph_b_s:0,paid_util_s:0,eutil_s:0,
    sc_s:0,s2f_s:0,s2o_s:0,o2f_s:0,oot_s:0,
    arp_s:0,dist_s:0,ppk_s:0,surge_s:0,ata_s:0,oar_s:0,par_s:0,rpr_s:0,
    dspend_s:0,dspend_w:0,sspend_s:0,sspend_w:0,bspend_s:0,bspend_w:0,
    dcc_s:0,dcc_w:0,sspend_ex_s:0,sspend_ex_w:0,
    oot_gs_s:0,oot_gs_w:0,ar_in_s:0,ar_in_w:0,ar_out_s:0,ar_out_w:0};
  for(const[,cm]of byP)for(const[,a]of cm)for(const k of Object.keys(st))st[k]+=a[k]||0;
  return Object.fromEntries(ALL_MK.map(k=>[k,accVal(st,k)]));
}

// ── FORMAT ────────────────────────────────────────────────────────────
function fNum(v,d=0){if(v==null||isNaN(v))return'—';return v.toLocaleString('en-GB',{minimumFractionDigits:d,maximumFractionDigits:d});}
function fGMV(v){if(v==null||isNaN(v))return'—';if(v>=1e6)return'€'+(v/1e6).toFixed(2)+' M';if(v>=1e3)return'€'+(v/1e3).toFixed(1)+' k';return'€'+fNum(v);}
function fPct(v){return v!=null?v.toFixed(1)+' %':'—';}
function fEur(v){return v!=null?'€'+v.toFixed(2):'—';}
function fKm(v) {return v!=null?v.toFixed(2)+' km':'—';}
function fRPH(v){return v!=null?v.toFixed(2):'—';}
function fH(v)  {return v!=null?v.toFixed(1)+' h':'—';}
function fSurge(v){return v!=null?v.toFixed(2)+'x':'—';}
function fATA(v){return v!=null?v.toFixed(1)+' min':'—';}
function fMetric(k,v){if(v==null||isNaN(v))return'—';
  return{f:()=>fNum(v),g:()=>fGMV(v),n:()=>fPct(v),o:()=>fNum(v)+' h',
    pa:()=>fNum(v),eph:()=>fEur(v),rph:()=>fRPH(v),hpad:()=>fH(v),util:()=>fPct(v),
    ar:()=>fNum(v),sess:()=>fNum(v),sc:()=>fPct(v),s2f:()=>fPct(v),s2o:()=>fPct(v),
    arp:()=>fEur(v),dist:()=>fKm(v),ppk:()=>fEur(v),surge:()=>fSurge(v),ata:()=>fATA(v),
    orders:()=>fNum(v),paid:()=>fH(v),eoh:()=>fH(v),nra:()=>fNum(v),
    oar:()=>fPct(v),par:()=>fPct(v),paid_util:()=>fPct(v),eutil:()=>fPct(v),
    eph_b:()=>fEur(v),o2f:()=>fPct(v),oot:()=>fPct(v),rpr:()=>v.toFixed(2),
    dspend:()=>fPct(v),sspend:()=>fPct(v),bspend:()=>fPct(v),dcc:()=>fPct(v),sspend_ex:()=>fPct(v),
    oot_gs:()=>fPct(v),ar_in:()=>fPct(v),ar_out:()=>fPct(v)}[k]?.()??v.toFixed(2);}
function pct(c,p){if(!p||p===0)return null;return(c-p)/Math.abs(p)*100;}
function mLabel(k){return{f:'Finished Orders',g:'GMV',n:'Net Rate %',o:'Online Hours',
  ap:'Active Partners',pa:'Partner Activations',eph:'EPH',rph:'RPH',hpad:'Hrs / Driver',util:'Utilisation',
  ar:'Active Riders',sess:'Sessions',sc:'Search Coverage',s2f:'S2F %',s2o:'S2O %',
  arp:'Avg Ride Price',dist:'Avg Distance',ppk:'Price / km',surge:'Surge',ata:'ATA (mins)',
  orders:'Orders',paid:'Paid Time (h)',eoh:'Effective OH',nra:'New Rider Act.',
  oar:'Order Accept. Rate',par:'Partner Accept. Rate',paid_util:'Paid Utilisation',
  eutil:'Eff. Utilisation',eph_b:'EPH (w/ bonuses)',o2f:'O2F %',oot:'Opt. Order Try %',
  rpr:'Rides / Active Rider',dspend:'Demand Spend %',sspend:'Supply Spend %',
  bspend:'Branding Spend %',dcc:'Dyn. Commission %',sspend_ex:'Supply Spend % (ex. brand)',
  oot_gs:'% Outside Search Radius',ar_in:'AR Inside Search Radius',ar_out:'AR Outside Search Radius'}[k]||k;}
function fMetricAp(k,v){if(v==null||isNaN(v))return'—';
  return{f:()=>fNum(v),g:()=>fGMV(v),n:()=>fPct(v),o:()=>fNum(v,0)+' h',
    ap:()=>fNum(v),pa:()=>fNum(v),eph:()=>fEur(v),rph:()=>fRPH(v),hpad:()=>fH(v),util:()=>fPct(v),
    ar:()=>fNum(v),sess:()=>fNum(v),sc:()=>fPct(v),s2f:()=>fPct(v),s2o:()=>fPct(v),
    arp:()=>fEur(v),dist:()=>fKm(v),ppk:()=>fEur(v),surge:()=>fSurge(v),ata:()=>fATA(v),
    orders:()=>fNum(v),paid:()=>fH(v),eoh:()=>fH(v),nra:()=>fNum(v),
    oar:()=>fPct(v),par:()=>fPct(v),paid_util:()=>fPct(v),eutil:()=>fPct(v),
    eph_b:()=>fEur(v),o2f:()=>fPct(v),oot:()=>fPct(v),rpr:()=>v.toFixed(2),
    dspend:()=>fPct(v),sspend:()=>fPct(v),bspend:()=>fPct(v),dcc:()=>fPct(v),sspend_ex:()=>fPct(v),
    oot_gs:()=>fPct(v),ar_in:()=>fPct(v),ar_out:()=>fPct(v)}[k]?.()??v.toFixed(2);}

// ── CITY PILLS ────────────────────────────────────────────────────────
function citySetEq(a,b){return a.length===b.length&&[...a].sort().every((c,i)=>[...b].sort()[i]===c);}
function renderPills(){
  const isAll=citySetEq(S.cities,ALL_CITIES),isExp=citySetEq(S.cities,EXPANSION),isRoS=citySetEq(S.cities,ROS);
  const isNone=S.cities.length===0;
  document.getElementById('city-pills').innerHTML=
    `<button class="pill pill-all pill-group${isAll?' active':' partial'}" onclick="setGroup('all')">All</button>`+
    `<button class="pill pill-group${isExp?' active':''}" onclick="setGroup('exp')">Expansion (${EXPANSION.length})</button>`+
    `<button class="pill pill-group${isRoS?' active':''}" onclick="setGroup('ros')">Rest of Spain (${ROS.length})</button>`+
    `<button class="pill${isNone?' active':''}" onclick="setGroup('none')" style="border-color:#ccc;color:#999">None</button>`+
    `<span class="pdivider"></span>`+
    ALL_CITIES.map(c=>`<button class="pill${S.cities.includes(c)?' active':''}" onclick="toggleCity('${c}')">${c}</button>`).join('');
}
function toggleCity(c){const i=S.cities.indexOf(c);if(i>=0)S.cities.splice(i,1);else S.cities.push(c);renderAll();}
function setGroup(g){S.cities=g==='all'?[...ALL_CITIES]:g==='exp'?[...EXPANSION]:g==='ros'?[...ROS]:[];renderAll();}

// ── KPI DATE RANGES ───────────────────────────────────────────────────
function kpiDateRange(){
  if(S.kpiMode==='range')return{from:S.df,to:S.dt};
  const lcp=lastPeriodInRange(S.gran,S.dt);
  return lcp?{from:lcp.from,to:lcp.to}:{from:S.df,to:S.dt};
}
function kpiPrevRange(){
  if(S.kpiMode==='range'){
    const a=new Date(S.df+'T00:00:00'),b=new Date(S.dt+'T00:00:00');
    const days=Math.round((b-a)/86400000)+1;
    const pe=new Date(a);pe.setDate(a.getDate()-1);
    const ps=new Date(pe);ps.setDate(pe.getDate()-days+1);
    return{from:fmtDate(ps),to:fmtDate(pe)};
  }
  return prevBeforeRange(S.gran,S.dt)||{from:S.df,to:S.dt};
}
function kpiPeriodLabel(){
  if(S.kpiMode==='range')return S.df+' → '+S.dt;
  const lcp=lastPeriodInRange(S.gran,S.dt);if(!lcp)return'';
  if(S.gran==='daily')return'Latest day: '+lcp.label;
  if(S.gran==='weekly')return'Latest week: '+periodLabel(lcp.label,'weekly');
  return'Latest month: '+periodLabel(lcp.label,'monthly');
}

// ── KPI CARDS ─────────────────────────────────────────────────────────
function renderKPIs(){
  const rng=kpiDateRange();
  const prng=yoyMode?yoyRange():kpiPrevRange();
  const cur=totals(aggregate(filteredRows(rng.from,rng.to)));
  const prv=totals(aggregate(filteredRows(prng.from,prng.to)));
  const pStr=kpiPeriodLabel();
  const vsLbl=yoyMode?'vs LY':'vs prev.';
  document.getElementById('kpi-row').innerHTML=
    [{k:'f',label:'Finished Orders'},{k:'g',label:'GMV'},{k:'n',label:'Net Rate (wtd. avg.)'},{k:'o',label:'Online Hours'},{k:'sess',label:'Sessions'}]
    .map(({k,label})=>{
      const val=cur[k];
      const ch=chgVal(k,val,prv[k]);
      const sub=ch!=null?`<div class="kpi-sub ${ch>=0?'kpi-up':'kpi-dn'}">${ch>=0?'↑':'↓'} ${chgStr(k,ch)} ${vsLbl}</div>`:'';
      const rocket=isATH(k,val)?` ${ROCKET}`:'';
      return`<div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-val">${fMetric(k,val)}${rocket}</div><div class="kpi-period">${pStr}</div>${sub}</div>`;
    }).join('');
}

// ── SECONDARY CARDS ───────────────────────────────────────────────────
function renderSecondary(){
  const rng=kpiDateRange(),prng=yoyMode?yoyRange():kpiPrevRange();
  const cur=secTotals(aggregate(filteredRows(rng.from,rng.to)));
  const prv=secTotals(aggregate(filteredRows(prng.from,prng.to)));
  function card(label,k,val,pval,fmt){
    const ch=chgVal(k,val,pval);
    const chg=ch!=null?`<div class="sc-chg ${ch>=0?'kpi-up':'kpi-dn'}">${ch>=0?'↑':'↓'} ${chgStr(k,ch)}</div>`:'';
    const rocket=isATH(k,val)?` ${ROCKET}`:'';
    return`<div class="sc-card"><div class="sc-label">${label}</div><div class="sc-val">${fmt(val)}${rocket}</div>${chg}</div>`;
  }
  document.getElementById('supply-cards').innerHTML=[
    card('Online Hours',         'o',   cur.o,    prv.o,    v=>fNum(v)+' h'),
    card('Partner Activations',  'pa',  cur.pa,   prv.pa,   v=>fNum(v)),
    card('EPH',                  'eph', cur.eph,  prv.eph,  fEur),
    card('RPH',                  'rph', cur.rph,  prv.rph,  fRPH),
    card('Hours / Active Driver','hpad',cur.hpad, prv.hpad, fH),
    card('Utilisation',          'util',cur.util, prv.util, fPct),
  ].join('');
  document.getElementById('demand-cards').innerHTML=[
    card('Active Riders',    'ar',  cur.ar,   prv.ar,   v=>fNum(v)),
    card('Search Coverage',  'sc',  cur.sc,   prv.sc,   fPct),
    card('Sessions',         'sess',cur.sess, prv.sess, v=>fNum(v)),
    card('Session to Finish','s2f', cur.s2f,  prv.s2f,  fPct),
    card('Session to Order', 's2o', cur.s2o,  prv.s2o,  fPct),
  ].join('');
  document.getElementById('pricing-cards').innerHTML=[
    card('Avg Ride Price','arp',  cur.arp,   prv.arp,   fEur),
    card('Avg Distance',  'dist', cur.dist,  prv.dist,  fKm),
    card('Price per km',  'ppk',  cur.ppk,   prv.ppk,   fEur),
    card('Surge',         'surge',cur.surge, prv.surge, fSurge),
    card('ATA',           'ata',  cur.ata,   prv.ata,   fATA),
  ].join('');
  document.getElementById('quality-cards').innerHTML=[
    card('O2F %',                  'o2f',    cur.o2f,    prv.o2f,    fPct),
    card('Order Accept. Rate',     'oar',    cur.oar,    prv.oar,    fPct),
    card('Partner Accept. Rate',   'par',    cur.par,    prv.par,    fPct),
    card('% Outside Search Radius','oot_gs', cur.oot_gs, prv.oot_gs, fPct),
    card('AR Inside Search Radius','ar_in',  cur.ar_in,  prv.ar_in,  fPct),
    card('AR Outside Search Radius','ar_out',cur.ar_out, prv.ar_out, fPct),
  ].join('');
}

// ── GENERIC SECTION CHART ─────────────────────────────────────────────
function renderSecPills(secId){
  const cfg=SECTIONS[secId],sel=SEC_SEL[secId];
  const clearBtn=secId==='general'
    ?`<button class="mcheck" onclick="clearSecSel('general')" style="border-color:#ccc;color:#999;margin-right:6px">✕ Clear</button>`:'';
  document.getElementById(secId+'-pills').innerHTML=clearBtn+cfg.metrics.map(m=>
    `<button class="mcheck${sel.includes(m.k)?' active':''}${m.bar?' mcheck-bar':''}" onclick="toggleSecMetric('${secId}','${m.k}')">
       <span class="mcheck-tick">✓</span> ${m.label}${m.bar?' ▐':''}
     </button>`
  ).join('');
}
function clearSecSel(secId){
  SEC_SEL[secId]=[];
  renderSecPills(secId);
  if(SECTIONS[secId].inst){SECTIONS[secId].inst.destroy();SECTIONS[secId].inst=null;}
  document.getElementById(secId+'-note').textContent='Select a metric above.';
}
function toggleSecMetric(secId,k){
  const sel=SEC_SEL[secId],i=sel.indexOf(k);
  if(i>=0){if(sel.length>1)sel.splice(i,1);}else sel.push(k);
  renderSecPills(secId);renderSecChart(secId);
}
function renderSecChart(secId){
  const cfg=SECTIONS[secId],sel=SEC_SEL[secId];
  if(sel.length===0){if(cfg.inst){cfg.inst.destroy();cfg.inst=null;}return;}
  const byP=aggregate(filteredRows());
  const periods=[...byP.keys()].sort();
  const labels=chartLabels(periods);
  const lineKs=sel.filter(k=>!cfg.metrics.find(m=>m.k===k)?.bar);
  const barKs =sel.filter(k=> cfg.metrics.find(m=>m.k===k)?.bar);
  const multiM=sel.length>1;
  const normalize=lineKs.length>1;
  const datasets=[];
  const secNormAvgs={};  // store per-metric avg for LY normalization

  if(multiM){
    // Aggregate across cities, one dataset per metric; colorIdx shared across line+bar
    let colorIdx=0;
    for(const k of lineKs){
      const agg=aggSum(byP,k);
      const pmap=Object.fromEntries(agg.map(d=>[d.pk,d.val]));
      let data=periods.map(p=>pmap[p]??null);
      const athFlags=data.map(v=>isATH(k,v));
      const rawData=data.slice();
      if(normalize){const vals=data.filter(v=>v!=null);const avg=vals.reduce((s,v)=>s+v,0)/(vals.length||1);secNormAvgs[k]=avg;data=data.map(v=>v!=null?(v/avg)*100:null);}
      const col=SEC_COLORS[colorIdx%SEC_COLORS.length];
      const dash=SEC_DASHES[colorIdx%SEC_DASHES.length];
      colorIdx++;
      datasets.push({label:mLabel(k),data,type:'line',yAxisID:'yLeft',
        borderColor:col,backgroundColor:col+'22',borderDash:dash,borderWidth:2.5,
        pointRadius:periods.length>90?0:3,pointHoverRadius:5,tension:.3,spanGaps:false,
        _athFlags:athFlags,_rawData:normalize?rawData:null,_mk:k});
    }
    for(const k of barKs){
      const agg=aggSum(byP,k);const pmap=Object.fromEntries(agg.map(d=>[d.pk,d.val]));
      const bData=periods.map(p=>pmap[p]??null);
      const col=SEC_COLORS[colorIdx%SEC_COLORS.length];colorIdx++;
      datasets.push({label:mLabel(k),data:bData,type:'bar',yAxisID:'yRight',
        backgroundColor:col+'55',borderColor:col,borderWidth:1.5,order:10,
        _athFlags:bData.map(v=>isATH(k,v)),_mk:k});
    }
  }else{
    // Single metric → per-city lines/bars
    const k=sel[0],isBar=cfg.metrics.find(m=>m.k===k)?.bar;
    S.cities.forEach((city,ci)=>{
      const agg=aggCity(byP,city,k);
      const pmap=Object.fromEntries(agg.map(d=>[d.pk,d.val]));
      const data=periods.map(p=>pmap[p]??null);
      const col=CITY_COLORS[city];
      const dash=SEC_DASHES[Math.floor(ci/SEC_COLORS.length)%SEC_DASHES.length];
      const athFlags=data.map(v=>isCityATH(city,k,v));
      if(isBar){
        datasets.push({label:city,data,type:'bar',yAxisID:'yRight',backgroundColor:col+'88',borderColor:col,borderWidth:1.5,order:10,_athFlags:athFlags,_mk:k});
      }else{
        datasets.push({label:city,data,type:'line',yAxisID:'yLeft',borderColor:col,backgroundColor:col+'22',borderDash:dash,borderWidth:2,
          pointRadius:periods.length>90?0:3,pointHoverRadius:5,tension:.3,spanGaps:false,_athFlags:athFlags,_mk:k});
      }
    });
  }

  // YoY overlay — dashed aggregate line per active line metric
  if(yoyMode){
    const yr=yoyRange();
    const byP_ly=aggregate(filteredRows(yr.from,yr.to));
    for(const k of lineKs){
      let lyData=periods.map(pk=>lyAggAtPeriod(byP_ly,lyPeriodKey(pk),k));
      if(normalize&&secNormAvgs[k]){const avg=secNormAvgs[k];lyData=lyData.map(v=>v!=null?(v/avg)*100:null);}
      const existingDs=datasets.find(d=>d._mk===k&&d.type==='line');
      const baseCol=(existingDs?.borderColor||'#888').replace(/[0-9a-f]{2}$/i,'');
      datasets.push({label:mLabel(k)+' (LY)',data:lyData,type:'line',yAxisID:'yLeft',
        borderColor:(existingDs?.borderColor||'#888')+'88',backgroundColor:'transparent',
        borderDash:[6,4],borderWidth:1.5,pointRadius:0,tension:.3,spanGaps:false,_mk:k});
    }
  }
  const showLeft=lineKs.length>0||(sel.length===1&&!cfg.metrics.find(m=>m.k===sel[0])?.bar);
  const showRight=barKs.length>0||(sel.length===1&&cfg.metrics.find(m=>m.k===sel[0])?.bar);
  const leftLabel=normalize?'Index (avg = 100)':'';
  document.getElementById(secId+'-note').textContent=
    normalize?'Multiple metrics — normalized (avg = 100). Hover to see real values.':
    multiM?'Aggregated across selected cities.':'';

  if(cfg.inst){cfg.inst.destroy();cfg.inst=null;}
  cfg.inst=new Chart(document.getElementById(secId+'-chart').getContext('2d'),{
    data:{labels,datasets},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{position:'bottom',labels:{boxWidth:12,font:{family:'Inter',size:10},color:'#444',
          generateLabels:chart=>chart.data.datasets.map((ds,i)=>({
            text:ds.label,fillStyle:ds.borderColor,strokeStyle:ds.borderColor,
            lineDash:ds.borderDash||[],lineWidth:2,hidden:false,index:i,datasetIndex:i
          }))}},
        tooltip:{backgroundColor:'#0C2C1C',titleFont:{family:'Inter',size:11},bodyFont:{family:'Inter',size:10},
          callbacks:{label:ctx=>{const v=ctx.parsed.y;
            const mk=ctx.dataset._mk||sel[0];
            if(normalize&&ctx.dataset.yAxisID==='yLeft'){
              const raw=ctx.dataset._rawData?.[ctx.dataIndex];
              return` ${ctx.dataset.label}: ${raw!=null?fMetric(mk,raw):'—'}`;
            }
            return` ${ctx.dataset.label}: ${v!=null?fMetric(mk,v):'—'}`;
          }}
        }
      },
      scales:{
        x:{grid:{color:'#F0F0F0'},ticks:{font:{family:'Inter',size:10},maxTicksLimit:16,maxRotation:45}},
        yLeft:{type:'linear',position:'left',display:showLeft,grid:{color:'#F0F0F0'},
          ticks:{font:{family:'Inter',size:10},callback:v=>{
            if(normalize)return v.toFixed(0);
            const k=lineKs[0]||sel[0];return k?fMetric(k,v):v;
          }},
          title:{display:!!leftLabel,text:leftLabel,font:{family:'Inter',size:10},color:'#666'}
        },
        yRight:{type:'linear',position:'right',display:showRight,grid:{drawOnChartArea:false},
          ticks:{font:{family:'Inter',size:10},callback:v=>v!=null?fMetric(barKs[0]||sel[0],v):''},
        }
      }
    }
  });
}

// ── MAIN CHART ────────────────────────────────────────────────────────
const METRIC_COLORS={f:'#2A9C64',g:'#0C2C1C',n:'#2A9C64',o:'#3B82F6',sess:'#F5B800'};
const METRIC_DASH  ={f:[],g:[6,4],o:[2,4],sess:[10,3]};
let mainChart=null;
function renderChart(){
  const rows=filteredRows(),byP=aggregate(rows),periods=[...byP.keys()].sort();
  const labels=chartLabels(periods);
  const lineMs=S.metrics.filter(m=>m!=='n'),hasNR=S.metrics.includes('n');
  const multiM=S.metrics.length>1,normalize=lineMs.length>1;
  const datasets=[];
  const normAvgs={};  // store per-metric avg for LY normalization
  if(multiM){
    for(const m of lineMs){
      const agg=aggSum(byP,m);const pmap=Object.fromEntries(agg.map(d=>[d.pk,d.val]));
      let data=periods.map(p=>pmap[p]??null);
      const athFlags=data.map(v=>isATH(m,v));
      const rawData=data.slice();
      if(normalize){const vals=data.filter(v=>v!=null);const avg=vals.reduce((s,v)=>s+v,0)/(vals.length||1);normAvgs[m]=avg;data=data.map(v=>v!=null?(v/avg)*100:null);}
      datasets.push({label:mLabel(m),data,type:'line',yAxisID:'yLeft',
        borderColor:METRIC_COLORS[m]||SEC_COLORS[lineMs.indexOf(m)%SEC_COLORS.length],
        backgroundColor:(METRIC_COLORS[m]||SEC_COLORS[lineMs.indexOf(m)%SEC_COLORS.length])+'22',
        borderDash:METRIC_DASH[m]||SEC_DASHES[lineMs.indexOf(m)%SEC_DASHES.length],
        borderWidth:2.5,pointRadius:periods.length>90?0:3,pointHoverRadius:5,tension:.3,spanGaps:false,
        _athFlags:athFlags,_rawData:normalize?rawData:null,_mk:m});
    }
    if(hasNR){const agg=aggSum(byP,'n');const pmap=Object.fromEntries(agg.map(d=>[d.pk,d.val]));
      const nrData=periods.map(p=>pmap[p]??null);
      datasets.push({label:'Net Rate %',data:nrData,type:'bar',yAxisID:'yRight',
        backgroundColor:'#2A9C6455',borderColor:'#2A9C64',borderWidth:1.5,order:10,_athFlags:nrData.map(v=>isATH('n',v)),_mk:'n'});}
  }else{
    const m=S.metrics[0];
    S.cities.forEach((city,ci)=>{
      const agg=aggCity(byP,city,m);const pmap=Object.fromEntries(agg.map(d=>[d.pk,d.val]));
      const data=periods.map(p=>pmap[p]??null),col=CITY_COLORS[city];
      const dash=SEC_DASHES[Math.floor(ci/SEC_COLORS.length)%SEC_DASHES.length];
      const athFlags=data.map(v=>isCityATH(city,m,v));
      if(m==='n'){datasets.push({label:city,data,type:'bar',yAxisID:'yRight',backgroundColor:col+'88',borderColor:col,borderWidth:1.5,order:10,_athFlags:athFlags,_mk:m});}
      else{datasets.push({label:city,data,type:'line',yAxisID:'yLeft',borderColor:col,backgroundColor:col+'22',borderDash:dash,borderWidth:2,
        pointRadius:periods.length>90?0:3,pointHoverRadius:5,tension:.3,spanGaps:false,_athFlags:athFlags,_mk:m});}
    });
  }
  // YoY overlay — dashed aggregate line per active line metric
  if(yoyMode){
    const yr=yoyRange();
    const byP_ly=aggregate(filteredRows(yr.from,yr.to));
    const metricsToOverlay=multiM?lineMs:(S.metrics[0]==='n'?[]:S.metrics);
    for(const m of metricsToOverlay){
      let lyData=periods.map(pk=>lyAggAtPeriod(byP_ly,lyPeriodKey(pk),m));
      // Apply same normalization as CY so both series share the same index scale
      if(normalize&&normAvgs[m]){
        const avg=normAvgs[m];
        lyData=lyData.map(v=>v!=null?(v/avg)*100:null);
      }
      const baseCol=METRIC_COLORS[m]||'#888';
      datasets.push({label:mLabel(m)+' (LY)',data:lyData,type:'line',yAxisID:'yLeft',
        borderColor:baseCol+'88',backgroundColor:'transparent',borderDash:[6,4],
        borderWidth:1.5,pointRadius:0,tension:.3,spanGaps:false,_mk:m,_rawData:null});
    }
  }
  const showLeft=lineMs.length>0,showRight=hasNR||S.metrics[0]==='n';
  const leftLabel=normalize?'Index (avg = 100)':(lineMs.length===1?mLabel(lineMs[0]):'');
  document.getElementById('chart-note').textContent=
    multiM&&normalize?'Multiple metrics — normalized (avg = 100). Hover to see real values.':multiM?'Aggregated across selected cities.':(yoyMode?'Solid = current year · Dashed = same period last year':'');
  if(mainChart){mainChart.destroy();mainChart=null;}
  mainChart=new Chart(document.getElementById('chart').getContext('2d'),{
    data:{labels,datasets},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{position:'bottom',labels:{boxWidth:12,font:{family:'Inter',size:11},color:'#444',
          generateLabels:chart=>chart.data.datasets.map((ds,i)=>({
            text:ds.label,fillStyle:ds.borderColor,strokeStyle:ds.borderColor,
            lineDash:ds.borderDash||[],lineWidth:2,hidden:false,index:i,datasetIndex:i
          }))}},
        tooltip:{backgroundColor:'#0C2C1C',titleFont:{family:'Inter',size:12},bodyFont:{family:'Inter',size:11},
          callbacks:{label:ctx=>{const v=ctx.parsed.y;
            const mk=ctx.dataset._mk||lineMs[0]||'f';
            if(normalize&&ctx.dataset.yAxisID==='yLeft'){
              const raw=ctx.dataset._rawData?.[ctx.dataIndex];
              return` ${ctx.dataset.label}: ${raw!=null?fMetric(mk,raw):'—'}`;
            }
            return` ${ctx.dataset.label}: ${v!=null?fMetric(mk,v):'—'}`;
          }}
        }
      },
      scales:{
        x:{grid:{color:'#F0F0F0'},ticks:{font:{family:'Inter',size:11},maxTicksLimit:20,maxRotation:45}},
        yLeft:{type:'linear',position:'left',display:showLeft,grid:{color:'#F0F0F0'},
          ticks:{font:{family:'Inter',size:11},callback:v=>{if(normalize)return v.toFixed(0);const mk=lineMs[0];if(!mk)return v;if(mk==='g')return fGMV(v);return fMetric(mk,v);}},
          title:{display:!!leftLabel,text:leftLabel,font:{family:'Inter',size:11},color:'#666'}},
        yRight:{type:'linear',position:'right',display:showRight,grid:{drawOnChartArea:false},
          ticks:{font:{family:'Inter',size:11},callback:v=>v!=null?fMetric('n',v):''},
          title:{display:showRight,text:'Net Rate %',font:{family:'Inter',size:11},color:'#666'}}
      }
    }
  });
}

// ── HISTORICAL PERFORMANCE TABLE ──────────────────────────────────────
const HIST_COLS=[
  {id:'main',   label:'Marketplace', cls:'sec-hdr-main',    metrics:[
    {k:'f',  label:'Finished Orders'},{k:'g',  label:'GMV'},
    {k:'n',  label:'Net Rate %'},     {k:'o',  label:'Online Hours'},
    {k:'sess',label:'Sessions'},
  ]},
  {id:'supply', label:'Supply',   cls:'sec-hdr-supply',  metrics:[
    {k:'ap', label:'Active Partners'},{k:'pa', label:'Partner Act.'},
    {k:'eph',label:'EPH'},            {k:'rph',label:'RPH'},
    {k:'hpad',label:'Hrs/Driver'},    {k:'util',label:'Utilisation'},
  ]},
  {id:'demand', label:'Demand',   cls:'sec-hdr-demand',  metrics:[
    {k:'ar', label:'Active Riders'},{k:'sess',label:'Sessions'},
    {k:'sc', label:'Search Cov.'},{k:'s2f',label:'S2F %'},{k:'s2o',label:'S2O %'},
  ]},
  {id:'pricing',label:'Pricing',  cls:'sec-hdr-pricing', metrics:[
    {k:'arp',label:'Avg Price'},{k:'dist',label:'Avg Dist.'},{k:'ppk',label:'Price/km'},{k:'surge',label:'Surge'},{k:'ata',label:'ATA'},
  ]},
  {id:'quality',label:'Quality',  cls:'sec-hdr-quality', metrics:[
    {k:'o2f',   label:'O2F %'},{k:'oar',   label:'OAR %'},{k:'par',   label:'PAR %'},
    {k:'oot_gs',label:'% Outsd.SR'},{k:'ar_in',label:'AR In SR'},{k:'ar_out',label:'AR Out SR'},
  ]},
];

// Metrics where change is expressed in percentage points (pp) not relative %
function isPct(k){return['n','util','sc','s2f','s2o','oar','paid_util','eutil','par','o2f','oot','dspend','sspend','bspend','dcc','sspend_ex','oot_gs','ar_in','ar_out'].includes(k);}
function chgVal(k,cur,prv){
  if(cur==null||prv==null)return null;
  if(isPct(k))return cur-prv;
  return prv===0?null:(cur-prv)/Math.abs(prv)*100;
}
function chgStr(k,ch){
  if(ch==null)return'—';
  return isPct(k)?(ch>=0?'+':'')+ch.toFixed(1)+' pp':(ch>=0?'+':'')+ch.toFixed(1)+'%';
}

// ── ALL-TIME-HIGH ─────────────────────────────────────────────────────
const ALL_MK=['f','g','n','o','ap','pa','eph','rph','hpad','util','ar','sess','sc','s2f','s2o','arp','dist','ppk','surge','ata','orders','paid','eoh','nra','oar','paid_util','eutil','eph_b','par','o2f','rpr','dspend','sspend','bspend','dcc','sspend_ex','oot','oot_gs','ar_in','ar_out'];

// GLOBAL_CITY_ATH: per-city ATH from the ENTIRE dataset (all cities, all dates).
// Recomputed only when granularity changes — never affected by city selection or date range.
let GLOBAL_CITY_ATH={};
let _athGran=null;
function computeGlobalCityATH(){
  if(S.gran===_athGran)return;          // skip if granularity hasn't changed
  _athGran=S.gran;
  GLOBAL_CITY_ATH={};
  const byP=aggregate(DATA);            // ALL rows, ALL cities, ALL dates
  for(const[,cm]of byP){
    for(const[city,a]of cm){
      if(!GLOBAL_CITY_ATH[city])GLOBAL_CITY_ATH[city]=Object.fromEntries(ALL_MK.map(k=>[k,null]));
      for(const k of ALL_MK){
        const v=accVal(a,k);
        if(v!=null&&(GLOBAL_CITY_ATH[city][k]==null||v>GLOBAL_CITY_ATH[city][k]))GLOBAL_CITY_ATH[city][k]=v;
      }
    }
  }
}

// ATH: group aggregate ATH for the SELECTED cities across all dates.
// Used for aggregate views (cards, table, multi-city charts).
let ATH={};
function computeATH(){
  const byP=aggregate(DATA.filter(r=>S.cities.includes(r.c)));
  ATH=Object.fromEntries(ALL_MK.map(k=>[k,null]));
  for(const[,cm]of byP){
    const merged=buildMerged(cm);
    for(const k of ALL_MK){const v=accVal(merged,k);if(v!=null&&(ATH[k]==null||v>ATH[k]))ATH[k]=v;}
  }
}

// isATH: for aggregate group values (cards, table, multi-city charts)
function isATH(k,v){return v!=null&&ATH[k]!=null&&v>=ATH[k]-1e-6;}
// isCityATH: for per-city values — always uses the city's global all-time high
function isCityATH(city,k,v){return v!=null&&GLOBAL_CITY_ATH[city]?.[k]!=null&&v>=GLOBAL_CITY_ATH[city][k]-1e-6;}
const ROCKET='🚀';

function buildMerged(cm){
  const m={f:0,g:0,ns:0,nw:0,o:0,ap:0,pa:0,ar:0,sess:0,
    orders:0,paid:0,eoh:0,nra:0,
    eph_s:0,rph_s:0,util_s:0,hpad_s:0,eph_b_s:0,paid_util_s:0,eutil_s:0,
    sc_s:0,s2f_s:0,s2o_s:0,o2f_s:0,oot_s:0,
    arp_s:0,dist_s:0,ppk_s:0,surge_s:0,ata_s:0,oar_s:0,par_s:0,rpr_s:0,
    dspend_s:0,dspend_w:0,sspend_s:0,sspend_w:0,bspend_s:0,bspend_w:0,
    dcc_s:0,dcc_w:0,sspend_ex_s:0,sspend_ex_w:0,
    oot_gs_s:0,oot_gs_w:0,ar_in_s:0,ar_in_w:0,ar_out_s:0,ar_out_w:0};
  for(const[,a]of cm)for(const k of Object.keys(m))m[k]+=a[k]||0;
  return m;
}

function renderHistoricalTable(){
  const byP=aggregate(filteredRows());
  const periods=[...byP.keys()].sort();               // ascending (oldest first)
  const totMap=new Map(periods.map(pk=>[pk,buildMerged(byP.get(pk))]));

  // Thead: row1 = section spans, row2 = metric names (val|Δ% each)
  let th1='<tr><th class="period-hdr" rowspan="2" style="min-width:36px;width:36px;left:0;position:sticky">Day</th><th class="period-hdr" rowspan="2" style="left:36px;position:sticky">Period</th>';
  let th2='<tr>';
  let _hci=0;
  for(const sec of HIST_COLS){
    th1+=`<th colspan="${sec.metrics.length*2}" class="metric-hdr ${sec.cls}">${sec.label}</th>`;
    for(const m of sec.metrics){
      const _hcs=_hci%2===0?'':'background:rgba(0,0,0,0.04)';
      _hci++;
      th2+=`<th class="metric-hdr" style="font-weight:600;${_hcs}">${m.label}</th><th class="metric-hdr" style="color:#888;${_hcs}">${yoyMode?'YoY':'Δ%'}</th>`;
    }
  }
  th1+='</tr>';th2+='</tr>';
  const thead='<thead>'+th1+th2+'</thead>';

  // Build LY lookup map when yoyMode
  let totMap_ly=null;
  if(yoyMode){
    const yr=yoyRange();
    const byP_ly=aggregate(filteredRows(yr.from,yr.to));
    totMap_ly=new Map([...byP_ly.keys()].map(pk=>[pk,buildMerged(byP_ly.get(pk))]));
  }

  // Tbody: oldest → newest
  let tbody='<tbody>';
  for(let i=0;i<periods.length;i++){
    const pk=periods[i];
    const cur=totMap.get(pk);
    // Previous period comparison
    let prev=null;
    if(yoyMode&&totMap_ly){
      prev=totMap_ly.get(lyPeriodKey(pk))||null;
    }else if(S.gran==='daily'){
      const d=new Date(pk+'T00:00:00');d.setDate(d.getDate()-7);
      const wkAgo=fmtDate(d);
      prev=totMap.has(wkAgo)?totMap.get(wkAgo):null;
    }else{
      prev=i>0?totMap.get(periods[i-1]):null;
    }
    const dayStr=S.gran==='daily'?['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][new Date(pk+'T00:00:00').getDay()]:'';
    let row=`<td class="hist-day">${dayStr}</td><td class="hist-period">${periodLabel(pk,S.gran)}</td>`;
    let _rci=0;
    for(const sec of HIST_COLS){
      for(const m of sec.metrics){
        const val=accVal(cur,m.k);
        const pval=prev?accVal(prev,m.k):null;
        // pp for % metrics, relative % for everything else
        const chg=(val==null||pval==null)?null:
          isPct(m.k)?(val-pval):(pval===0?null:(val-pval)/Math.abs(pval)*100);
        const chgCls=chg==null?'chg-nil':chg>=0?'chg-pos':'chg-neg';
        const chgStr=chg==null?'—':
          isPct(m.k)?((chg>=0?'+':'')+chg.toFixed(1)+' pp'):
          ((chg>=0?'+':'')+chg.toFixed(1)+'%');
        const rkt=isATH(m.k,val)?` ${ROCKET}`:'';
        const _rcs=_rci%2===0?'':'background:rgba(0,0,0,0.035)';
        _rci++;
        row+=`<td class="hist-val" style="${_rcs}">${fMetricAp(m.k,val)}${rkt}</td><td class="hist-chg ${chgCls}" style="${_rcs}">${chgStr}</td>`;
      }
    }
    tbody+=`<tr data-pk="${pk}">${row}</tr>`;
  }
  tbody+='</tbody>';
  document.getElementById('hist-tbl').innerHTML=thead+tbody;
  document.getElementById('hist-note').textContent=
    `${periods.length} periods · aggregated across ${S.cities.length} cit${S.cities.length===1?'y':'ies'} · ${S.df} → ${S.dt}`;

  // Scroll to bottom so the most recent rows are visible by default
  const histScroll=document.querySelector('.hist-scroll');
  if(histScroll) requestAnimationFrame(()=>{histScroll.scrollTop=histScroll.scrollHeight;});

  // Hover: also highlight the same weekday from the previous week (daily mode only)
  if(S.gran==='daily'){
    const tbody_el=document.querySelector('#hist-tbl tbody');
    if(tbody_el){
      tbody_el.addEventListener('mouseover',e=>{
        const row=e.target.closest('tr');
        if(!row||!row.dataset.pk) return;
        const d=new Date(row.dataset.pk+'T00:00:00');
        d.setDate(d.getDate()-7);
        const prevPk=fmtDate(d);
        tbody_el.querySelectorAll('tr.hist-prev-hl').forEach(r=>r.classList.remove('hist-prev-hl'));
        const prevRow=tbody_el.querySelector(`tr[data-pk="${prevPk}"]`);
        if(prevRow) prevRow.classList.add('hist-prev-hl');
      });
      tbody_el.addEventListener('mouseleave',()=>{
        tbody_el.querySelectorAll('tr.hist-prev-hl').forEach(r=>r.classList.remove('hist-prev-hl'));
      });
    }
  }
}

// ── EVENT HANDLERS ────────────────────────────────────────────────────
function setGran(btn){document.querySelectorAll('.seg-btn[data-g]').forEach(b=>b.classList.remove('active'));btn.classList.add('active');S.gran=btn.dataset.g;renderAll();}
function setKpiMode(btn){document.querySelectorAll('.seg-btn[data-km]').forEach(b=>b.classList.remove('active'));btn.classList.add('active');S.kpiMode=btn.dataset.km;renderKPIs();renderSecondary();}
function toggleMetric(btn){
  const m=btn.dataset.m,i=S.metrics.indexOf(m);
  if(i>=0){if(S.metrics.length>1)S.metrics.splice(i,1);}else S.metrics.push(m);
  document.querySelectorAll('.mcheck[data-m]').forEach(b=>b.classList.toggle('active',S.metrics.includes(b.dataset.m)));
  renderChart();
}
function onDate(){S.df=document.getElementById('df').value;S.dt=document.getElementById('dt').value;renderAll();}

// ── YEAR OVER YEAR ────────────────────────────────────────────────────
let yoyMode=false;
function toggleYoY(){
  yoyMode=!yoyMode;
  document.getElementById('yoy-btn').classList.toggle('active',yoyMode);
  const grp=document.getElementById('kpi-mode-grp');
  grp.style.opacity=yoyMode?'0.4':'1';
  grp.style.pointerEvents=yoyMode?'none':'';
  renderAll();
}
function yoyRange(){
  const days=S.gran==='monthly'?365:364;
  const d1=new Date(S.df+'T00:00:00'),d2=new Date(S.dt+'T00:00:00');
  d1.setDate(d1.getDate()-days);d2.setDate(d2.getDate()-days);
  return{from:fmtDate(d1),to:fmtDate(d2)};
}
function lyPeriodKey(pk){
  if(S.gran==='weekly'){const[y,w]=pk.split('-W');return(parseInt(y)-1)+'-W'+w;}
  if(S.gran==='monthly'){const[y,m]=pk.split('-');return(parseInt(y)-1)+'-'+m;}
  const d=new Date(pk+'T00:00:00');d.setDate(d.getDate()-364);return fmtDate(d);
}
function lyAggAtPeriod(byP_ly,pk,k){
  const cm=byP_ly.get(pk);if(!cm)return null;
  return accVal(buildMerged(cm),k);
}

// ── PRICING SECTION ───────────────────────────────────────────────────
const _pCharts = {};
const UBER_COLOR = 'rgba(156,163,175,0.85)';   // gray
const CAB_COLOR  = 'rgba(196,167,240,0.85)';   // light purple

// Track whether user has manually picked a city in the pricing dropdown.
// Resets to false whenever the main city selection changes.
let _pCityOverride = false;

function _populatePRegion(city){
  const sel = document.getElementById('p-region');
  if(!sel) return;
  sel.innerHTML='';
  const cfg = PRICING_DATA[city];
  if(!cfg) return;
  cfg.regions.forEach(r=>{
    const o=document.createElement('option');
    o.value=r; o.textContent=r;
    if(r===cfg.default_region) o.selected=true;
    sel.appendChild(o);
  });
}

function onPCity(){
  _pCityOverride = true;
  const city = document.getElementById('p-city').value;
  _populatePRegion(city);
  renderPricing();
}

function initPricingCity(){
  const cs = document.getElementById('p-city');
  if(!cs) return;
  cs.innerHTML='';
  const cities = Object.keys(PRICING_DATA);
  if(!cities.length){
    document.getElementById('pricing-section').style.display='none';
    return;
  }
  cities.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;cs.appendChild(o);});
  syncPricingCity();
}

// Called from renderAll() every time the main city selection changes.
function syncPricingCity(){
  _pCityOverride = false;
  const pCityEl = document.getElementById('p-city');
  if(!pCityEl) return;
  if(S.cities.length === 1 && PRICING_DATA[S.cities[0]]){
    pCityEl.value = S.cities[0];
    _populatePRegion(S.cities[0]);
  }
  renderPricing();
}

function renderPricing(){
  const body = document.getElementById('pricing-body');
  if(!body) return;

  // If multiple cities selected and user hasn't manually overridden → show prompt
  if(S.cities.length !== 1 && !_pCityOverride){
    ['pc-wd','pc-we'].forEach(id=>{if(_pCharts[id]){_pCharts[id].destroy();delete _pCharts[id];}});
    body.innerHTML='<div style="color:var(--muted);padding:32px 0;text-align:center;font-size:14px">Select a single city above to view pricing data.</div>';
    return;
  }

  const city   = document.getElementById('p-city').value;
  const region = document.getElementById('p-region').value;
  const cfg    = PRICING_DATA[city];

  if(!cfg||!cfg.data){
    body.innerHTML='<div style="color:var(--muted);padding:24px 0;text-align:center">No pricing data available for this city.</div>';
    return;
  }
  const rows = (cfg.data[region]||[]);
  if(!rows.length){
    body.innerHTML='<div style="color:var(--muted);padding:24px 0;text-align:center">No data available for '+region+'.</div>';
    return;
  }

  // Destroy old charts
  ['pc-wd','pc-we'].forEach(id=>{if(_pCharts[id]){_pCharts[id].destroy();delete _pCharts[id];}});

  const labels = rows.map(r=>r.date);   // Monday date as X-axis label
  const uberWd = rows.map(r=>r.uber_wd);
  const uberWe = rows.map(r=>r.uber_we);
  const cabWd  = rows.map(r=>r.cab_wd);
  const cabWe  = rows.map(r=>r.cab_we);

  function fmt(v){return v==null?'N/A':(v>0?'+':'')+v.toFixed(1)+'%';}

  body.innerHTML=`
    <div class="pgap-grid">
      <div class="pgap-card">
        <div class="pgap-title">Weekdays — Surge Included</div>
        <div class="pgap-chart-wrap"><canvas id="pc-wd"></canvas></div>
        <div class="pgap-legend">
          <span class="pgap-dot" style="background:${UBER_COLOR}"></span>Uber
          <span class="pgap-dot" style="background:${CAB_COLOR};margin-left:12px"></span>Cabify
          <span style="color:var(--muted);font-size:11px;margin-left:12px">Positive = Bolt more expensive</span>
        </div>
      </div>
      <div class="pgap-card">
        <div class="pgap-title">Weekends — Surge Included</div>
        <div class="pgap-chart-wrap"><canvas id="pc-we"></canvas></div>
        <div class="pgap-legend">
          <span class="pgap-dot" style="background:${UBER_COLOR}"></span>Uber
          <span class="pgap-dot" style="background:${CAB_COLOR};margin-left:12px"></span>Cabify
          <span style="color:var(--muted);font-size:11px;margin-left:12px">Positive = Bolt more expensive</span>
        </div>
      </div>
    </div>`;

  function makeChart(canvasId, ds1, ds1Label, ds1Color, ds2, ds2Label, ds2Color){
    const ctx=document.getElementById(canvasId).getContext('2d');
    _pCharts[canvasId]=new Chart(ctx,{
      type:'bar',
      data:{
        labels,
        datasets:[
          {label:ds1Label, data:ds1, backgroundColor:ds1Color, borderRadius:3},
          {label:ds2Label, data:ds2, backgroundColor:ds2Color, borderRadius:3},
        ]
      },
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{
          legend:{display:false},
          tooltip:{callbacks:{label:c=>c.dataset.label+': '+fmt(c.raw)}}
        },
        scales:{
          x:{
            grid:{display:false},
            ticks:{color:'var(--muted)',font:{size:10},maxRotation:45}
          },
          y:{
            grid:{color:'rgba(150,150,150,0.12)'},
            ticks:{color:'var(--muted)',font:{size:10},callback:v=>(v>0?'+':'')+v+'%'}
          }
        }
      }
    });
  }
  makeChart('pc-wd', uberWd,'Uber',UBER_COLOR, cabWd,'Cabify',CAB_COLOR);
  makeChart('pc-we', uberWe,'Uber',UBER_COLOR, cabWe,'Cabify',CAB_COLOR);
}

// ── INIT ──────────────────────────────────────────────────────────────
function renderAll(){
  computeGlobalCityATH();
  computeATH();
  renderPills();renderKPIs();renderSecondary();renderChart();
  for(const id of['supply','demand','pricing','quality','general']){renderSecPills(id);renderSecChart(id);}
  renderHistoricalTable();
  // Hide pricing gap section when YoY mode is active
  const ps=document.getElementById('pricing-section');
  if(ps) ps.style.display=yoyMode?'none':'';
  if(!yoyMode) syncPricingCity();
}
document.getElementById('nav-badge').textContent='Data up to '+new Date(DATA_MAX+'T00:00:00').toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
renderAll();
initPricingCity();
</script>
</body>
</html>"""

html = (TMPL
    .replace('__DATA__',         data_json)
    .replace('__CITIES__',       cities_json)
    .replace('__COLORS__',       colors_json)
    .replace('__EXPANSION__',    expansion_json)
    .replace('__ROS__',          ros_json)
    .replace('__PRICING_DATA__', pricing_json)
    .replace('__MIN_DATE__',     min_date)
    .replace('__MAX_DATE__',     max_date)
    .replace('__DEFAULT_FROM__', default_from)
)

out = os.environ.get('OUTPUT_PATH', '/sessions/busy-eager-einstein/mnt/outputs/bolt_dashboard.html')
if os.path.dirname(out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✓ Dashboard v6 generated — {os.path.getsize(out)//1024} KB")
print(f"  {len(data)} rows · {len(all_cities)} cities · {min_date} → {max_date}")
