"""Minimal browser UI to run the buy-vs-rent simulation."""
from __future__ import annotations

from typing import Dict, Optional

from flask import Flask, render_template_string, request

from simulation import ScenarioParams, simulate_break_even

app = Flask(__name__)

# Defaults mirror the CLI defaults in simulation.py
DEFAULTS: Dict[str, float] = {
    "purchase_price": 1_200_000,
    "down_payment": 240_000,
    "term_years": 30,
    "home_appreciation": 0.015,
    "investment_return": 0.075,
    "inflation": 0.03,
    "rent_monthly": 5_500,
    "maintenance_monthly": 2_200,
    "insurance_monthly": 150,
    "other_owner_costs_monthly": 150,
    "rent_growth": 0.035,
    "maintenance_growth": 0.035,
    "insurance_growth": 0.03,
    "other_owner_costs_growth": 0.03,
    "buy_closing_cost_pct": 0.02,
    "sell_cost_pct": 0.06,
    "max_years": 30,
}


def parse_variable_schedule(schedule_str: str) -> Optional[list[tuple[int, float]]]:
    """Parse 'start_month:rate' comma-separated pairs."""
    schedule = []
    for item in schedule_str.split(","):
        item = item.strip()
        if not item:
            continue
        start_str, rate_str = item.split(":")
        schedule.append((int(start_str), float(rate_str)))
    return schedule or None


def form_to_params(form) -> ScenarioParams:
    fixed_rate = form.get("fixed_mortgage_rate")
    fixed = float(fixed_rate) if fixed_rate else None

    variable_schedule = None
    if fixed is None:
        variable_schedule = parse_variable_schedule(
            form.get("variable_rate_schedule", "0:0.065,24:0.075,60:0.060")
        )

    return ScenarioParams(
        purchase_price=float(form.get("purchase_price", DEFAULTS["purchase_price"])),
        down_payment=float(form.get("down_payment", DEFAULTS["down_payment"])),
        term_years=int(form.get("term_years", DEFAULTS["term_years"])),
        home_appreciation=float(form.get("home_appreciation", DEFAULTS["home_appreciation"])),
        investment_return=float(form.get("investment_return", DEFAULTS["investment_return"])),
        inflation=float(form.get("inflation", DEFAULTS["inflation"])),
        fixed_mortgage_rate=fixed,
        variable_rate_schedule=variable_schedule,
        rent_monthly=float(form.get("rent_monthly", DEFAULTS["rent_monthly"])),
        maintenance_monthly=float(form.get("maintenance_monthly", DEFAULTS["maintenance_monthly"])),
        insurance_monthly=float(form.get("insurance_monthly", DEFAULTS["insurance_monthly"])),
        other_owner_costs_monthly=float(
            form.get("other_owner_costs_monthly", DEFAULTS["other_owner_costs_monthly"])
        ),
        rent_growth=float(form.get("rent_growth", DEFAULTS["rent_growth"])),
        maintenance_growth=float(form.get("maintenance_growth", DEFAULTS["maintenance_growth"])),
        insurance_growth=float(form.get("insurance_growth", DEFAULTS["insurance_growth"])),
        other_owner_costs_growth=float(
            form.get("other_owner_costs_growth", DEFAULTS["other_owner_costs_growth"])
        ),
        buy_closing_cost_pct=float(form.get("buy_closing_cost_pct", DEFAULTS["buy_closing_cost_pct"])),
        sell_cost_pct=float(form.get("sell_cost_pct", DEFAULTS["sell_cost_pct"])),
        max_years=int(form.get("max_years", DEFAULTS["max_years"])),
        report_real=form.get("report_mode", "real") == "real",
    )


TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Buy vs Rent Simulation</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 32px; max-width: 960px; }
      h1 { margin-bottom: 8px; }
      p.lead { margin-top: 0; color: #444; }
      ul.key-points { margin-top: 0; }
      .section { margin: 12px 0 20px; }
      form { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px 16px; }
      fieldset { border: 1px solid #ddd; padding: 12px; border-radius: 6px; background: #fafafa; }
      legend { font-weight: 700; padding: 0 6px; }
      .group { grid-column: 1 / -1; }
      label { display: block; font-weight: 600; margin-bottom: 4px; }
      input { width: 100%; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; }
      .chip { display: inline-block; padding: 2px 6px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-left: 6px; }
      .chip-owner { background: #e6edff; color: #1236a3; border: 1px solid #c5d5ff; }
      .chip-renter { background: #e5f7ec; color: #186a3b; border: 1px solid #c2e8d0; }
      .chip-both { background: #f3f3f3; color: #444; border: 1px solid #d8d8d8; }
      .row { grid-column: 1 / -1; }
      .error { color: #b30000; font-weight: 600; }
      .result { margin-top: 16px; padding: 16px; background: #f5f5f5; border-radius: 6px; border: 1px solid #e6e6e6; }
      .pill-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 12px; }
      .pill { background: white; border: 1px solid #dcdcdc; border-radius: 6px; padding: 12px; }
      .pill-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; color: #666; margin-bottom: 4px; }
      .table { width: 100%; border-collapse: collapse; margin-top: 10px; }
      .table th, .table td { border: 1px solid #ddd; padding: 6px 8px; text-align: right; font-variant-numeric: tabular-nums; }
      .table th { text-align: left; background: #f0f0f0; }
      .helper { color: #444; font-size: 14px; margin: 4px 0 0; }
      .inline-code { font-family: Menlo, Consolas, monospace; background: #f0f0f0; padding: 2px 4px; border-radius: 4px; }
      button { padding: 10px 16px; font-size: 16px; border: none; background: #1652f0; color: white; border-radius: 6px; cursor: pointer; }
      button:hover { background: #0f3db3; }
      .muted { color: #555; }
    </style>
  </head>
  <body>
    <h1>Buy vs Rent Simulation</h1>
    <p class="lead">Enter your assumptions, run the month-by-month simulation, and see when owning equals renting (after accounting for home equity vs. invested cash while renting).</p>
    <div class="section">
      <strong>How it works</strong>
      <ul class="key-points">
        <li>Every month we compare owner costs (mortgage + carrying costs) to rent. The cheaper side invests the difference at your investment return.</li>
        <li>Your down payment and buy closing costs stay invested while renting; home value and mortgage balance track owner equity.</li>
        <li>Break-even occurs when owner net worth (home equity + any invested savings) catches up to the renter’s portfolio in real or nominal dollars.</li>
      </ul>
      <div class="helper">Tip: use the rate schedule format <span class="inline-code">start_month:annual_rate</span> (e.g., <span class="inline-code">0:0.065,24:0.075,60:0.060</span>) for variable mortgages. Chips mark whether an input impacts the Owner, Renter, or Both.</div>
    </div>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST">
      {% for group in groups %}
        <fieldset class="group">
          <legend>{{ group.title }} {% if group.scope %}<span class="chip chip-{{ group.scope|lower }}">{{ group.scope }}</span>{% endif %}</legend>
          {% if group.description %}<div class="helper" style="margin-bottom: 8px;">{{ group.description }}</div>{% endif %}
          {% for field in group.fields %}
            <div>
              <label for="{{ field.name }}">{{ field.label }} <span class="chip chip-{{ field.scope|lower }}">{{ field.scope }}</span></label>
              <input type="text" id="{{ field.name }}" name="{{ field.name }}" value="{{ request.form.get(field.name, field.value) }}">
            </div>
          {% endfor %}
        </fieldset>
      {% endfor %}
      <fieldset class="group">
        <legend>Mortgage Rate <span class="chip chip-owner">Owner</span></legend>
        <div class="row">
          <label>Mode</label>
          <div>
            <label><input type="radio" name="rate_mode" value="variable" {% if not request.form.get('fixed_mortgage_rate') %}checked{% endif %}> Variable (use schedule)</label>
            <label><input type="radio" name="rate_mode" value="fixed" {% if request.form.get('fixed_mortgage_rate') %}checked{% endif %}> Fixed</label>
          </div>
        </div>
        <div>
          <label for="fixed_mortgage_rate">Fixed mortgage rate (annual decimal)</label>
          <input type="text" id="fixed_mortgage_rate" name="fixed_mortgage_rate" value="{{ request.form.get('fixed_mortgage_rate', '') }}">
        </div>
        <div>
          <label for="variable_rate_schedule">Variable rate schedule (start_month:annual_rate)</label>
          <input type="text" id="variable_rate_schedule" name="variable_rate_schedule" value="{{ request.form.get('variable_rate_schedule', '0:0.065,24:0.075,60:0.060') }}">
        </div>
      </fieldset>
      <fieldset class="group">
        <legend>Reporting</legend>
        <label><input type="radio" name="report_mode" value="real" {% if request.form.get('report_mode', 'real') == 'real' %}checked{% endif %}> Inflation-adjusted (real)</label>
        <label><input type="radio" name="report_mode" value="nominal" {% if request.form.get('report_mode') == 'nominal' %}checked{% endif %}> Nominal</label>
      </fieldset>
      <div class="row">
        <button type="submit">Run simulation</button>
      </div>
    </form>

    {% if result %}
      <div class="result">
        <h2 style="margin: 0 0 8px 0;">Results</h2>
        {% if result.break_even_month is not none %}
          <div><strong>Break-even:</strong> month {{ result.break_even_month }} (~{{ "%.2f"|format(result.break_even_years) }} years) comparing {{ "real" if result.used_real_dollars else "nominal" }} dollars.</div>
        {% else %}
          <div><strong>No break-even within horizon.</strong> Owner never catches renter under these assumptions.</div>
        {% endif %}
        <div class="pill-grid">
          <div class="pill">
            <div class="pill-label">Upfront cash to buy</div>
            <div>${{ "{:,.0f}".format(result.assumptions.upfront_buy_cash) }}</div>
            <div class="helper">Includes down payment + closing (${{
              "{:,.0f}".format(result.assumptions.buy_closing_cost) }})</div>
          </div>
          <div class="pill">
            <div class="pill-label">Mortgage rate mode</div>
            <div>{% if request.form.get('fixed_mortgage_rate') %}Fixed @ {{ request.form.get('fixed_mortgage_rate') }}{% else %}Variable schedule{% endif %}</div>
            <div class="helper">{% if request.form.get('fixed_mortgage_rate') %}Fixed rate overrides schedule{% else %}{{ request.form.get('variable_rate_schedule', '0:0.065,24:0.075,60:0.060') }}{% endif %}</div>
          </div>
          <div class="pill">
            <div class="pill-label">Comparison dollars</div>
            <div>{{ "Inflation-adjusted (real)" if result.used_real_dollars else "Nominal" }}</div>
            <div class="helper">Toggle under Reporting</div>
          </div>
          {% if breakeven_row %}
            <div class="pill">
              <div class="pill-label">Net worth at break-even</div>
              <div>Owner ${{ "{:,.0f}".format(breakeven_row.nw_buy) }} | Renter ${{ "{:,.0f}".format(breakeven_row.nw_rent) }}</div>
              <div class="helper">Home value ${{ "{:,.0f}".format(breakeven_row.home_value) }} | Mortgage balance ${{ "{:,.0f}".format(breakeven_row.mortgage_balance) }}</div>
            </div>
          {% endif %}
        </div>
        {% if checkpoints %}
          <div style="margin-top: 12px; font-weight: 700;">Yearly checkpoints (real/nominal matches your reporting choice)</div>
          <table class="table">
            <thead>
              <tr>
                <th>Month</th>
                <th>Rate</th>
                <th>Owner outflow</th>
                <th>Rent</th>
                <th>Owner net worth</th>
                <th>Renter net worth</th>
                <th>Home value</th>
                <th>Mortgage bal.</th>
              </tr>
            </thead>
            <tbody>
              {% for row in checkpoints %}
                <tr>
                  <td>{{ row.month }}</td>
                  <td>{{ "%.3f"|format(row.mortgage_rate) }}</td>
                  <td>${{ "{:,.0f}".format(row.owner_outflow) }}</td>
                  <td>${{ "{:,.0f}".format(row.rent) }}</td>
                  <td>${{ "{:,.0f}".format(row.nw_buy) }}</td>
                  <td>${{ "{:,.0f}".format(row.nw_rent) }}</td>
                  <td>${{ "{:,.0f}".format(row.home_value) }}</td>
                  <td>${{ "{:,.0f}".format(row.mortgage_balance) }}</td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
          <div class="helper">Checkpoints include month 0, each anniversary, and the break-even month if it lands between years.</div>
        {% endif %}
      </div>
    {% endif %}
  </body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    if request.method == "POST":
        try:
            params = form_to_params(request.form)
            # If user selected fixed mode but left field blank, raise a clearer error
            if request.form.get("rate_mode") == "fixed" and params.fixed_mortgage_rate is None:
                raise ValueError("Provide a fixed mortgage rate or switch to variable.")
            result = simulate_break_even(params)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

    def field(name: str, label: str, value, scope: str) -> dict:
        return {"name": name, "label": label, "value": value, "scope": scope}

    groups = [
        {
            "title": "Owner: Purchase & Loan",
            "scope": "Owner",
            "description": "One-time costs and mortgage structure for the owner path.",
            "fields": [
                field("purchase_price", "Purchase price ($)", DEFAULTS["purchase_price"], "Owner"),
                field("down_payment", "Down payment ($)", DEFAULTS["down_payment"], "Owner"),
                field("term_years", "Term (years)", DEFAULTS["term_years"], "Owner"),
                field("buy_closing_cost_pct", "Buy closing cost pct (decimal of price)", DEFAULTS["buy_closing_cost_pct"], "Owner"),
                field("sell_cost_pct", "Sell cost pct (decimal of price)", DEFAULTS["sell_cost_pct"], "Owner"),
            ],
        },
        {
            "title": "Owner: Monthly carrying costs",
            "scope": "Owner",
            "description": "Recurring owner-only costs.",
            "fields": [
                field("maintenance_monthly", "Maintenance ($/mo)", DEFAULTS["maintenance_monthly"], "Owner"),
                field("insurance_monthly", "Insurance ($/mo)", DEFAULTS["insurance_monthly"], "Owner"),
                field("other_owner_costs_monthly", "Other owner costs ($/mo)", DEFAULTS["other_owner_costs_monthly"], "Owner"),
            ],
        },
        {
            "title": "Renter: Monthly cost",
            "scope": "Renter",
            "description": "Baseline rent before growth.",
            "fields": [
                field("rent_monthly", "Rent ($/mo)", DEFAULTS["rent_monthly"], "Renter"),
            ],
        },
        {
            "title": "Growth assumptions",
            "scope": "Both",
            "description": "Annual growth on prices and costs; chips mark which path is affected.",
            "fields": [
                field("home_appreciation", "Home appreciation (annual decimal)", DEFAULTS["home_appreciation"], "Owner"),
                field("rent_growth", "Rent growth (annual decimal)", DEFAULTS["rent_growth"], "Renter"),
                field("maintenance_growth", "Maintenance growth (annual decimal)", DEFAULTS["maintenance_growth"], "Owner"),
                field("insurance_growth", "Insurance growth (annual decimal)", DEFAULTS["insurance_growth"], "Owner"),
                field(
                    "other_owner_costs_growth",
                    "Other owner costs growth (annual decimal)",
                    DEFAULTS["other_owner_costs_growth"],
                    "Owner",
                ),
            ],
        },
        {
            "title": "Returns, inflation, and horizon",
            "scope": "Both",
            "description": "Shared settings that drive both scenarios.",
            "fields": [
                field("investment_return", "Investment return (annual decimal)", DEFAULTS["investment_return"], "Both"),
                field("inflation", "Inflation (annual decimal)", DEFAULTS["inflation"], "Both"),
                field("max_years", "Max horizon (years)", DEFAULTS["max_years"], "Both"),
            ],
        },
    ]

    # Convert dict to an object with attribute access for templating
    class AttrView(dict):
        __getattr__ = dict.get

    # Allow attribute-style access for template readability
    result_obj = AttrView(result) if result else None
    assumptions_obj = AttrView(result["assumptions"]) if result else None
    breakeven_row = None
    checkpoints = []
    if result_obj:
        result_obj.assumptions = assumptions_obj
        breakeven_month = result_obj.get("break_even_month")
        for row in result_obj.get("history", []):
            if breakeven_month is not None and row.get("month") == breakeven_month:
                breakeven_row = AttrView(row)
                break
        checkpoints = [AttrView(row) for row in result_obj.get("history", [])[-6:]]

    return render_template_string(
        TEMPLATE,
        groups=groups,
        request=request,
        result=result_obj,
        error=error,
        breakeven_row=breakeven_row,
        checkpoints=checkpoints,
    )


if __name__ == "__main__":
    app.run(debug=True)
