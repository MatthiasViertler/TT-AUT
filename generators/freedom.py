"""
Freedom Dashboard HTML generator.

Produces users/{person}/output/{person}_{year}_freedom.html — a self-contained interactive
page pre-populated with actual dividend data from this run.

Slider defaults come from config freedom_dashboard section:
  portfolio_eur, monthly_expenses_eur, monthly_contribution_eur,
  yield_pct, growth_pct

Interactive sliders drive:
  - Freedom % gauge and progress bar
  - Milestones (25 / 50 / 75 / 100% free)
  - 40-year passive income projection chart
  - Estimated portfolio value
"""

import json
from decimal import Decimal
from pathlib import Path

from core.models import NormalizedTransaction, TaxSummary, TransactionType

ZERO = Decimal("0")

_FD_DEFAULTS = {
    "portfolio_eur": 10000,
    "monthly_expenses_eur": 2000,
    "monthly_contribution_eur": 500,
    "yield_pct": 3.0,
    "growth_pct": 7.0,
}


def write_freedom_html(
    transactions: list[NormalizedTransaction],
    summary: TaxSummary,
    path: Path,
    config: dict,
) -> None:
    fd = {**_FD_DEFAULTS, **config.get("freedom_dashboard", {})}
    total_div = float(summary.total_dividends_eur)

    # Use computed portfolio value if available, else fall back to config.
    # portfolio_eur_supplement adds a manually-specified amount on top of the computed
    # value (e.g. SAXO broker value that can't yet be auto-computed).
    supplement = int(fd.get("portfolio_eur_supplement", 0))
    computed = summary.portfolio_eur_computed
    if computed is not None and computed > ZERO:
        portfolio_eur = int(computed) + supplement
        portfolio_source = "computed+manual" if supplement else "computed"
    else:
        portfolio_eur = int(fd["portfolio_eur"])
        portfolio_source = "config"

    # Slider max: at least 2× the portfolio value (min 2M, step to next round million)
    slider_max = max(2_000_000, portfolio_eur * 3)
    # Round up to nearest million for a clean slider range
    slider_max = ((slider_max + 999_999) // 1_000_000) * 1_000_000

    # Recompute yield against the full portfolio (IBKR + supplement).
    # summary.dividend_yield_computed uses only the IBKR-computed base and would be
    # inflated when a supplement is present (e.g. 4.42% on €331k vs 2.43% on €603k).
    if computed is not None and computed > ZERO and total_div > 0:
        yield_pct_val = total_div / portfolio_eur * 100.0
        yield_source = "computed"
    elif summary.dividend_yield_computed is not None:
        yield_pct_val = summary.dividend_yield_computed
        yield_source = "computed"
    else:
        yield_pct_val = float(fd["yield_pct"])
        yield_source = "config"

    # Build portfolio_positions JSON from summary
    portfolio_json = [
        {
            "symbol": p.symbol,
            "fund_type": p.fund_type,
            "qty": float(p.qty),
            "is_synthetic": p.is_synthetic,
            "eur_value": float(p.eur_value),
            "dividends_eur": float(p.dividends_eur),
            "yield_pct": p.yield_pct,
            "portfolio_pct": p.portfolio_pct,
        }
        for p in summary.portfolio_positions
    ]

    # Keep holdings for backward-compat (subtitle count uses it)
    holdings = _build_holdings(transactions, summary.tax_year)

    interest_eur    = float(summary.interest_eur)
    wht_total       = float(summary.total_wht_paid_eur)
    wht_creditable  = float(summary.wht_creditable_eur)
    wht_excess      = max(0.0, wht_total - wht_creditable)
    gross_income    = total_div + interest_eur
    # Net cash = gross × 72.5% minus non-creditable (excess) WHT already paid
    net_income      = max(0.0, gross_income * 0.725 - wht_excess)

    data = {
        "person": summary.person_label,
        "year": summary.tax_year,
        "total_dividends_eur": round(total_div, 2),
        "monthly_dividends_eur": round(total_div / 12, 2),
        "interest_eur": round(interest_eur, 2),
        "wht_total_eur": round(wht_total, 2),
        "wht_creditable_eur": round(wht_creditable, 2),
        "wht_excess_eur": round(wht_excess, 2),
        "net_income_eur": round(net_income, 2),
        "net_monthly_income_eur": round(net_income / 12, 2),
        "holdings": holdings,
        "portfolio_positions": portfolio_json,
        "defaults": {
            "portfolio_eur": portfolio_eur,
            "portfolio_source": portfolio_source,
            "portfolio_slider_max": slider_max,
            "monthly_expenses_eur": int(fd["monthly_expenses_eur"]),
            "monthly_contribution_eur": int(fd["monthly_contribution_eur"]),
            "yield_pct": yield_pct_val,
            "yield_source": yield_source,
            "growth_pct": float(fd["growth_pct"]),
        },
    }

    html = _HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    path.write_text(html, encoding="utf-8")


def _build_holdings(txns: list[NormalizedTransaction], tax_year: int) -> list[dict]:
    acc: dict[str, dict] = {}
    for t in txns:
        if t.trade_date.year != tax_year:
            continue
        if t.txn_type != TransactionType.DIVIDEND:
            continue
        if t.symbol not in acc:
            acc[t.symbol] = {
                "symbol": t.symbol,
                "description": t.description or t.symbol,
                "isin": t.isin or "",
                "dividends_eur": ZERO,
                "wht_eur": ZERO,
                "payments": 0,
            }
        h = acc[t.symbol]
        h["dividends_eur"] += t.eur_amount or ZERO
        h["wht_eur"] += t.eur_wht or ZERO
        h["payments"] += 1

    result = sorted(acc.values(), key=lambda x: x["dividends_eur"], reverse=True)
    for h in result:
        h["dividends_eur"] = round(float(h["dividends_eur"]), 2)
        h["wht_eur"] = round(float(h["wht_eur"]), 2)
    return result


# ── HTML template ─────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Freedom Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: system-ui, -apple-system, sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  min-height: 100vh;
  padding: 1.5rem;
}
.header { margin-bottom: 1.5rem; }
.header h1 { font-size: 1.5rem; font-weight: 700; color: #f8fafc; }
.header .subtitle { color: #64748b; font-size: 0.875rem; margin-top: 0.25rem; }

.cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.card {
  background: #1e293b;
  border-radius: 0.75rem;
  padding: 1.25rem;
  border: 1px solid #334155;
}
.card-label {
  font-size: 0.7rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.5rem;
}
.card-value { font-size: 1.75rem; font-weight: 700; }
.card-sub { font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem; }

.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}
.panel {
  background: #1e293b;
  border-radius: 0.75rem;
  padding: 1.25rem;
  border: 1px solid #334155;
}
.panel-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 1.25rem;
}

/* Sliders */
.slider-row { margin-bottom: 1rem; }
.slider-row.divider { border-top: 1px solid #334155; padding-top: 1rem; margin-top: 0.25rem; }
.slider-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.8125rem;
  margin-bottom: 0.4rem;
}
.slider-label .name { color: #cbd5e1; }
.slider-label .val  { color: #10b981; font-weight: 600; }
input[type=range] {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: #334155;
  outline: none;
  cursor: pointer;
  -webkit-appearance: none;
}
input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: #10b981;
  cursor: pointer;
}
input[type=range]::-moz-range-thumb {
  width: 16px; height: 16px;
  border-radius: 50%;
  background: #10b981;
  border: none;
  cursor: pointer;
}
.sl-portfolio-thumb::-webkit-slider-thumb { background: #60a5fa; }
.sl-portfolio-thumb::-moz-range-thumb     { background: #60a5fa; }

/* Freedom bar */
.freedom-bar-wrap { margin-top: 1.25rem; }
.freedom-bar-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 0.4rem;
}
.freedom-bar-outer {
  background: #334155;
  border-radius: 999px;
  height: 10px;
  overflow: hidden;
}
.freedom-bar-inner {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #10b981, #34d399);
  transition: width 0.3s ease;
}

/* Milestones */
.milestones {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.625rem;
  margin-top: 1rem;
}
.milestone {
  background: #0f172a;
  border-radius: 0.5rem;
  padding: 0.75rem 0.375rem;
  text-align: center;
  border: 1px solid #334155;
}
.milestone.achieved {
  border-color: #10b981;
  background: rgba(16,185,129,0.08);
}
.milestone .m-pct  { font-size: 0.9375rem; font-weight: 700; color: #10b981; }
.milestone .m-name { font-size: 0.625rem; color: #64748b; margin-top: 0.125rem; }
.milestone .m-yr   { font-size: 0.75rem; color: #94a3b8; margin-top: 0.3rem; }
.milestone.achieved .m-yr { color: #10b981; }

/* Chart */
.chart-container { position: relative; height: 290px; }

/* Holdings table */
.holdings-panel { margin-bottom: 1.5rem; }
.holdings-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.holdings-table th {
  text-align: left;
  color: #64748b;
  font-weight: 500;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #334155;
  white-space: nowrap;
}
.holdings-table th.r { text-align: right; }
.holdings-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #1e293b;
  color: #cbd5e1;
  vertical-align: middle;
}
.holdings-table td.r { text-align: right; }
.holdings-table tr:last-child td { border-bottom: none; }
.holdings-table tr:hover td { background: rgba(255,255,255,0.02); }
.sym { font-weight: 700; color: #f8fafc; }
.isin { color: #475569; font-size: 0.7rem; font-family: monospace; }
.bar-cell { display: flex; align-items: center; gap: 0.5rem; justify-content: flex-end; }
.bar-mini { height: 6px; border-radius: 3px; background: #2E75B6; min-width: 2px; }

.footer {
  text-align: center;
  color: #334155;
  font-size: 0.75rem;
  padding-top: 0.5rem;
}
</style>
</head>
<body>
<script>const DATA = __DATA_JSON__;</script>

<div class="header">
  <h1>&#127807; Freedom Dashboard</h1>
  <div class="subtitle" id="subtitle"></div>
</div>

<div class="cards">
  <div class="card">
    <div class="card-label">Annual Dividends (gross)</div>
    <div class="card-value" style="color:#10b981" id="c-annual"></div>
    <div class="card-sub">before tax, <span id="c-year"></span></div>
  </div>
  <div class="card">
    <div class="card-label">Net Monthly Income</div>
    <div class="card-value" style="color:#60a5fa" id="c-monthly"></div>
    <div class="card-sub">after KeSt &amp; WHT</div>
  </div>
  <div class="card">
    <div class="card-label">Financial Freedom</div>
    <div class="card-value" id="c-freedom"></div>
    <div class="card-sub" id="c-freedom-sub"></div>
  </div>
  <div class="card">
    <div class="card-label">FIRE in</div>
    <div class="card-value" style="color:#f59e0b" id="c-fire-years"></div>
    <div class="card-sub" id="c-fire-sub"></div>
  </div>
</div>

<!-- Tax Breakdown -->
<div class="panel" style="margin-bottom:1.5rem" id="tax-breakdown-panel">
  <div class="panel-title">Income After Tax &mdash; Tax Year <span id="breakdown-tax-year"></span></div>
  <table class="holdings-table" id="tax-breakdown-table">
    <thead>
      <tr>
        <th>Source</th>
        <th class="r">Gross</th>
        <th class="r">WHT paid</th>
        <th class="r">AT KeSt (net)</th>
        <th class="r">Net cash</th>
      </tr>
    </thead>
    <tbody id="tax-breakdown-body"></tbody>
    <tfoot id="tax-breakdown-foot"></tfoot>
  </table>
  <div style="font-size:0.75rem;color:#64748b;margin-top:0.625rem" id="tax-breakdown-note"></div>
</div>

<div class="main-grid">
  <!-- Left: sliders + milestones -->
  <div class="panel">
    <div class="panel-title">Portfolio &amp; Assumptions</div>

    <div class="slider-row">
      <div class="slider-label">
        <span class="name">Current portfolio value <span id="port-badge" style="font-size:0.65rem;padding:1px 5px;border-radius:3px;margin-left:4px"></span></span>
        <span class="val" id="l-portfolio"></span>
      </div>
      <input type="range" id="sl-portfolio" class="sl-portfolio-thumb"
             min="1000" max="5000000" step="1000">
    </div>

    <div class="slider-row divider">
      <div class="slider-label">
        <span class="name">Monthly expenses target</span>
        <span class="val" id="l-expenses"></span>
      </div>
      <input type="range" id="sl-expenses" min="500" max="10000" step="100">
    </div>
    <div class="slider-row">
      <div class="slider-label">
        <span class="name">Monthly contribution</span>
        <span class="val" id="l-contrib"></span>
      </div>
      <input type="range" id="sl-contrib" min="0" max="5000" step="50">
    </div>
    <div class="slider-row">
      <div class="slider-label">
        <span class="name">Portfolio yield (dividends) <span id="yield-badge" style="font-size:0.65rem;padding:1px 5px;border-radius:3px;margin-left:4px"></span></span>
        <span class="val" id="l-yield"></span>
      </div>
      <input type="range" id="sl-yield" min="1" max="8" step="0.1">
    </div>
    <div class="slider-row">
      <div class="slider-label">
        <span class="name">Annual portfolio growth</span>
        <span class="val" id="l-growth"></span>
      </div>
      <input type="range" id="sl-growth" min="0" max="12" step="0.5">
    </div>

    <div class="freedom-bar-wrap">
      <div class="freedom-bar-header">
        <span>Net income coverage (post-tax vs. monthly target)</span>
        <span id="l-bar-pct"></span>
      </div>
      <div class="freedom-bar-outer">
        <div class="freedom-bar-inner" id="freedom-bar" style="width:0%"></div>
      </div>
    </div>

    <div class="milestones">
      <div class="milestone" id="m25">
        <div class="m-pct">25%</div>
        <div class="m-name">Quarter Free</div>
        <div class="m-yr" id="m25-yr"></div>
      </div>
      <div class="milestone" id="m50">
        <div class="m-pct">50%</div>
        <div class="m-name">Half Free</div>
        <div class="m-yr" id="m50-yr"></div>
      </div>
      <div class="milestone" id="m75">
        <div class="m-pct">75%</div>
        <div class="m-name">Almost Free</div>
        <div class="m-yr" id="m75-yr"></div>
      </div>
      <div class="milestone" id="m100">
        <div class="m-pct">FIRE &#128293;</div>
        <div class="m-name">Fully Free</div>
        <div class="m-yr" id="m100-yr"></div>
      </div>
    </div>
  </div>

  <!-- Right: projection chart -->
  <div class="panel">
    <div class="panel-title">Income Projection &mdash; Total Return (dividends + growth)</div>
    <div class="chart-container">
      <canvas id="projChart"></canvas>
    </div>
  </div>
</div>

<!-- Portfolio Holdings -->
<div class="panel holdings-panel">
  <div class="panel-title">Portfolio Holdings &mdash; 31 Dec <span id="h-year"></span></div>
  <table class="holdings-table">
    <thead>
      <tr>
        <th>Symbol</th>
        <th>Type</th>
        <th class="r">Qty</th>
        <th class="r">EUR Value</th>
        <th class="r">Port%</th>
        <th class="r">Divs EUR</th>
        <th class="r">Yield%</th>
      </tr>
    </thead>
    <tbody id="h-body"></tbody>
    <tfoot id="h-foot"></tfoot>
  </table>
  <div id="h-note" style="font-size:0.75rem;color:#64748b;margin-top:0.5rem"></div>
</div>

<div class="footer">
  Generated by Kapitalertrag &nbsp;&middot;&nbsp; Informational only &mdash; verify with your tax consultant
</div>

<script>
const E = id => document.getElementById(id);
const eur  = n => '\\u20ac' + n.toLocaleString('de-AT', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const eurK = n => {
  if (n >= 1000000) return '\\u20ac' + (n/1000000).toLocaleString('de-AT', {minimumFractionDigits:1, maximumFractionDigits:1}) + 'M';
  if (n >= 1000)    return '\\u20ac' + (n/1000).toLocaleString('de-AT', {minimumFractionDigits:1, maximumFractionDigits:1}) + 'k';
  return eur(n);
};
const pct = (n, d=1) => n.toLocaleString('de-AT', {minimumFractionDigits: d, maximumFractionDigits: d}) + '%';

// Init slider values from defaults (portfolio_eur may be computed from FIFO)
const sl = E('sl-portfolio');
sl.max   = DATA.defaults.portfolio_slider_max;
sl.step  = Math.max(1000, Math.round(DATA.defaults.portfolio_slider_max / 1000 / 10) * 10);
sl.value = DATA.defaults.portfolio_eur;
E('sl-expenses').value  = DATA.defaults.monthly_expenses_eur;
E('sl-contrib').value   = DATA.defaults.monthly_contribution_eur;
E('sl-yield').value     = DATA.defaults.yield_pct;
E('sl-growth').value    = DATA.defaults.growth_pct;

// Badge: show whether portfolio value was auto-computed or from config
const badge = E('port-badge');
if (DATA.defaults.portfolio_source === 'computed') {
  badge.textContent = 'auto';
  badge.style.background = 'rgba(16,185,129,0.2)';
  badge.style.color = '#10b981';
  badge.title = 'Portfolio value computed from remaining FIFO lots \xd7 Dec 31 market prices';
} else {
  badge.textContent = 'config';
  badge.style.background = 'rgba(100,116,139,0.2)';
  badge.style.color = '#64748b';
  badge.title = 'Portfolio value from config (portfolio_eur) — set computed value by running with all broker files';
}

// Badge: show whether yield was auto-computed (trailing) or from config
const yieldBadge = E('yield-badge');
if (DATA.defaults.yield_source === 'computed') {
  yieldBadge.textContent = 'auto';
  yieldBadge.style.background = 'rgba(16,185,129,0.2)';
  yieldBadge.style.color = '#10b981';
  yieldBadge.title = 'Trailing yield computed from actual dividends \xf7 Dec 31 portfolio value';
} else {
  yieldBadge.textContent = 'config';
  yieldBadge.style.background = 'rgba(100,116,139,0.2)';
  yieldBadge.style.color = '#64748b';
  yieldBadge.title = 'Yield from config (yield_pct) — run with all broker files for computed value';
}

// Static header — DATA.year is the tax year (e.g. 2025); used wherever the year
// appears as display text. Adding more spans with these IDs just works automatically.
E('c-year').textContent           = DATA.year;
E('breakdown-tax-year').textContent = DATA.year;
E('c-annual').textContent  = eur(DATA.total_dividends_eur);
E('c-monthly').textContent = eur(DATA.net_monthly_income_eur);

// ── Tax Breakdown table ───────────────────────────────────────────────────────
(function() {
  const divGross  = DATA.total_dividends_eur;
  const intGross  = DATA.interest_eur;
  const whtTotal  = DATA.wht_total_eur;
  const whtCred   = DATA.wht_creditable_eur;
  const whtExcess = DATA.wht_excess_eur;
  const netIncome = DATA.net_income_eur;
  const kestNet   = Math.max(0, (divGross + intGross) * 0.275 - whtCred);

  const tbody = E('tax-breakdown-body');

  function addRow(label, gross, wht, kest, net) {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td>' + label + '</td>' +
      '<td class="r">' + eur(gross) + '</td>' +
      '<td class="r" style="color:#f59e0b">' + (wht > 0.005 ? '\\u2212' + eur(wht) : '\\u2014') + '</td>' +
      '<td class="r" style="color:#f59e0b">' + (kest > 0.005 ? '\\u2212' + eur(kest) : '\\u2014') + '</td>' +
      '<td class="r" style="color:#10b981">' + eur(net) + '</td>';
    tbody.appendChild(tr);
  }

  if (divGross > 0) {
    const dKest = Math.max(0, divGross * 0.275 - whtCred);
    addRow('Dividends', divGross, whtTotal, dKest, divGross - whtTotal - dKest);
  }
  if (intGross > 0.005) {
    const iKest = intGross * 0.275;
    addRow('Cash interest (IBKR)', intGross, 0, iKest, intGross - iKest);
  }

  const tfoot = E('tax-breakdown-foot');
  const tfr = document.createElement('tr');
  tfr.style.fontWeight = '600';
  tfr.style.borderTop  = '1px solid #334155';
  tfr.innerHTML =
    '<td>TOTAL</td>' +
    '<td class="r">' + eur(divGross + intGross) + '</td>' +
    '<td class="r" style="color:#f59e0b">' + (whtTotal > 0.005 ? '\\u2212' + eur(whtTotal) : '\\u2014') + '</td>' +
    '<td class="r" style="color:#f59e0b">\\u2212' + eur(kestNet) + '</td>' +
    '<td class="r" style="color:#10b981;font-size:1rem">' + eur(netIncome) + '</td>';
  tfoot.appendChild(tfr);

  if (whtExcess > 0.05) {
    E('tax-breakdown-note').innerHTML =
      '\\u26a0 Excess WHT (non-creditable, beyond AT treaty rate): <strong style="color:#f59e0b">' +
      eur(whtExcess) + '</strong> \\u2014 reclaimable from source countries (1\\u20132 yr lag, separate filing required).';
  } else if ((divGross + intGross) === 0) {
    E('tax-breakdown-panel').style.display = 'none';
  }
})();

const nValued = DATA.portfolio_positions.filter(p => !p.is_synthetic && p.eur_value > 0).length;
const nDivs   = DATA.portfolio_positions.filter(p => p.dividends_eur > 0).length;
E('subtitle').textContent =
  DATA.person + '  \\u00b7  Tax Year ' + DATA.year + '  \\u00b7  ' +
  nValued + ' positions valued  \\u00b7  ' + nDivs + ' paying dividends';

// Portfolio Holdings table
E('h-year').textContent = DATA.year;
const totalPortEur = DATA.portfolio_positions.reduce((s, p) => s + p.eur_value, 0);
const totalDivEur  = DATA.portfolio_positions.reduce((s, p) => s + p.dividends_eur, 0);
const hbody = E('h-body');
let synthCount = 0;

DATA.portfolio_positions.forEach(p => {
  if (p.is_synthetic) synthCount++;
  const tr = document.createElement('tr');
  const qtyStr = p.is_synthetic ? ('~' + Math.round(p.qty)) : (p.qty > 0 ? Math.round(p.qty).toLocaleString('de-AT') : '\\u2014');
  const valStr = p.eur_value > 0 ? eur(p.eur_value) : '\\u2014';
  const pctStr = p.portfolio_pct != null ? pct(p.portfolio_pct) : '\\u2014';
  const divStr = p.dividends_eur > 0 ? eur(p.dividends_eur) : '\\u2014';
  const yldStr = p.yield_pct != null ? pct(p.yield_pct, 1) : '\\u2014';
  const yldStyle = p.yield_pct > 5 ? 'color:#10b981;font-weight:600' : '';
  tr.innerHTML =
    '<td class="sym">' + p.symbol + '</td>' +
    '<td style="color:#64748b;font-size:0.75rem">[' + p.fund_type + ']</td>' +
    '<td class="r"' + (p.is_synthetic ? ' style="color:#64748b"' : '') + '>' + qtyStr + '</td>' +
    '<td class="r">' + valStr + '</td>' +
    '<td class="r">' + pctStr + '</td>' +
    '<td class="r" style="color:#10b981">' + divStr + '</td>' +
    '<td class="r" style="' + yldStyle + '">' + yldStr + '</td>';
  hbody.appendChild(tr);
});

// Totals footer
const overallYield = totalPortEur > 0 ? totalDivEur / totalPortEur * 100 : null;
const tfoot = E('h-foot');
const tfr = document.createElement('tr');
tfr.style.fontWeight = '600';
tfr.style.borderTop = '1px solid #334155';
tfr.innerHTML =
  '<td colspan="3">TOTAL</td>' +
  '<td class="r">' + eur(totalPortEur) + '</td>' +
  '<td class="r">100%</td>' +
  '<td class="r" style="color:#10b981">' + eur(totalDivEur) + '</td>' +
  '<td class="r">' + (overallYield != null ? pct(overallYield, 1) : '\\u2014') + '</td>';
tfoot.appendChild(tfr);

if (synthCount > 0) {
  E('h-note').textContent = '\\u26a0 ' + synthCount + ' synthetic position(s) shown with ~qty \\u2014 EUR value not computable (SAXO AggregatedAmounts or manual_cost_basis lots)';
}

// Chart
const ctx = E('projChart').getContext('2d');
let chart = null;

function project(portfolioStart, monthlyExp, monthlyContrib, yieldPct, growthPct) {
  const targetAnnual  = monthlyExp * 12;
  const yieldRate     = yieldPct / 100;
  const growthRate    = growthPct / 100;
  const annualContrib = monthlyContrib * 12;

  const labels = [], income = [], divOnly = [];
  const ms = {25: null, 50: null, 75: null, 100: null};
  let portfolio = portfolioStart;

  for (let yr = 0; yr <= 40; yr++) {
    // Total return = dividends + capital growth (sustainable withdrawal without depleting capital)
    const totalReturn = portfolio * (yieldRate + growthRate);
    const dividends   = portfolio * yieldRate;
    labels.push(yr === 0 ? 'Now' : '+' + yr + 'y');
    income.push(Math.round(totalReturn));
    divOnly.push(Math.round(dividends));
    const p = targetAnnual > 0 ? totalReturn / targetAnnual * 100 : 0;
    [25, 50, 75, 100].forEach(m => { if (ms[m] === null && p >= m) ms[m] = yr; });
    portfolio = portfolio * (1 + growthRate) + annualContrib;
  }
  return { labels, income, divOnly, ms, targetAnnual };
}

function update() {
  const portfolioStart = +E('sl-portfolio').value;
  const monthlyExp     = +E('sl-expenses').value;
  const monthlyContrib = +E('sl-contrib').value;
  const yieldPct       = +E('sl-yield').value;
  const growthPct      = +E('sl-growth').value;

  E('l-portfolio').textContent = eurK(portfolioStart);
  E('l-expenses').textContent  = eur(monthlyExp) + '/mo';
  E('l-contrib').textContent   = eur(monthlyContrib) + '/mo';
  E('l-yield').textContent     = pct(yieldPct);
  E('l-growth').textContent    = pct(growthPct);

  const { labels, income, divOnly, ms, targetAnnual } = project(
    portfolioStart, monthlyExp, monthlyContrib, yieldPct, growthPct
  );

  // Freedom card (current net income vs target — uses post-tax spendable amount)
  const freedomPct = monthlyExp > 0
    ? Math.min(DATA.net_monthly_income_eur / monthlyExp * 100, 999)
    : 0;
  const freedomEl = E('c-freedom');
  freedomEl.textContent = pct(Math.min(freedomPct, 100));
  freedomEl.style.color = freedomPct >= 100 ? '#10b981' : freedomPct >= 50 ? '#60a5fa' : '#f59e0b';
  E('c-freedom-sub').textContent = eur(DATA.net_monthly_income_eur) + ' net of ' + eur(monthlyExp) + ' goal';

  // FIRE card (based on total return: dividends + portfolio growth)
  const fireYr = ms[100];
  const fireEl = E('c-fire-years');
  if (fireYr === 0) {
    fireEl.textContent = 'Now!';
    fireEl.style.color = '#10b981';
    E('c-fire-sub').textContent = 'Total return covers expenses';
  } else if (fireYr !== null) {
    fireEl.textContent = fireYr + ' yr' + (fireYr === 1 ? '' : 's');
    fireEl.style.color = fireYr <= 15 ? '#10b981' : '#f59e0b';
    const fireYear = new Date().getFullYear() + fireYr;
    E('c-fire-sub').textContent = 'Total return: target ' + fireYear;
  } else {
    fireEl.textContent = '> 40 yrs';
    fireEl.style.color = '#ef4444';
    E('c-fire-sub').textContent = 'Increase contribution or growth';
  }

  // Freedom bar
  const barPct = Math.min(freedomPct, 100);
  E('freedom-bar').style.width = barPct + '%';
  E('l-bar-pct').textContent   = pct(barPct);

  // Milestones — use net income (post-tax) for achievement check
  const currentPct = targetAnnual > 0 ? DATA.net_income_eur / targetAnnual * 100 : 0;
  [25, 50, 75, 100].forEach(m => {
    const el   = E('m' + m);
    const yrEl = E('m' + m + '-yr');
    if (currentPct >= m) {
      el.classList.add('achieved');
      yrEl.textContent = '\\u2713 achieved';
    } else {
      el.classList.remove('achieved');
      const yr = ms[m];
      yrEl.textContent = yr !== null
        ? (yr === 0 ? 'this year' : 'in ' + yr + ' yr' + (yr === 1 ? '' : 's'))
        : '> 40 yrs';
    }
  });

  // Chart
  const targetLine = labels.map(() => Math.round(targetAnnual));
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Total Return (yield + growth)',
          data: income,
          borderColor: '#10b981',
          backgroundColor: 'rgba(16,185,129,0.12)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: 'Dividends only',
          data: divOnly,
          borderColor: '#60a5fa',
          backgroundColor: 'transparent',
          borderDash: [4, 3],
          fill: false,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 1.5,
        },
        {
          label: 'FIRE target (' + eur(monthlyExp) + '/mo)',
          data: targetLine,
          borderColor: '#f59e0b',
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: c => ' ' + eur(c.parsed.y) + '/year'
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', font: { size: 10 }, maxTicksLimit: 11 },
          grid: { color: 'rgba(51,65,85,0.6)' }
        },
        y: {
          ticks: {
            color: '#64748b',
            font: { size: 10 },
            callback: v => v >= 1000 ? '\\u20ac' + Math.round(v/1000) + 'k' : '\\u20ac' + v
          },
          grid: { color: 'rgba(51,65,85,0.6)' }
        }
      }
    }
  });
}

['sl-portfolio','sl-expenses','sl-contrib','sl-yield','sl-growth'].forEach(id => {
  E(id).addEventListener('input', update);
});
update();
</script>
</body>
</html>
"""
