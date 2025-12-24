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
      body { font-family: Arial, sans-serif; margin: 32px; max-width: 800px; }
      form { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px 16px; }
      fieldset { border: 1px solid #ddd; padding: 12px; border-radius: 6px; }
      legend { font-weight: 700; padding: 0 6px; }
      .group { grid-column: 1 / -1; }
      label { display: block; font-weight: 600; margin-bottom: 4px; }
      input { width: 100%; padding: 6px 8px; }
      .row { grid-column: 1 / -1; }
      .error { color: #b30000; font-weight: 600; }
      .result { margin-top: 16px; padding: 12px; background: #f5f5f5; border-radius: 6px; }
    </style>
  </head>
  <body>
    <h1>Buy vs Rent Simulation</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST">
      {% for group in groups %}
        <fieldset class="group">
          <legend>{{ group.title }}</legend>
          {% for field, label, value in group.fields %}
            <div>
              <label for="{{ field }}">{{ label }}</label>
              <input type="text" id="{{ field }}" name="{{ field }}" value="{{ request.form.get(field, value) }}">
            </div>
          {% endfor %}
        </fieldset>
      {% endfor %}
      <fieldset class="group">
        <legend>Mortgage Rate</legend>
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
        {% if result.break_even_month is not none %}
          <div><strong>Break-even:</strong> month {{ result.break_even_month }} (~{{ "%.2f"|format(result.break_even_years) }} years), compared in {{ "real" if result.used_real_dollars else "nominal" }} dollars.</div>
        {% else %}
          <div><strong>No break-even within horizon.</strong></div>
        {% endif %}
        <div style="margin-top:8px;"><strong>Assumptions:</strong> Upfront cash ${{ "%.0f"|format(result.assumptions.upfront_buy_cash) }}, closing cost ${{ "%.0f"|format(result.assumptions.buy_closing_cost) }}</div>
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

    groups = [
        {
            "title": "Purchase & Loan",
            "fields": [
                ("purchase_price", "Purchase price ($)", DEFAULTS["purchase_price"]),
                ("down_payment", "Down payment ($)", DEFAULTS["down_payment"]),
                ("term_years", "Term (years)", DEFAULTS["term_years"]),
                ("buy_closing_cost_pct", "Buy closing cost pct (decimal of price)", DEFAULTS["buy_closing_cost_pct"]),
                ("sell_cost_pct", "Sell cost pct (decimal of price)", DEFAULTS["sell_cost_pct"]),
            ],
        },
        {
            "title": "Monthly Costs",
            "fields": [
                ("rent_monthly", "Rent ($/mo)", DEFAULTS["rent_monthly"]),
                ("maintenance_monthly", "Maintenance ($/mo)", DEFAULTS["maintenance_monthly"]),
                ("insurance_monthly", "Insurance ($/mo)", DEFAULTS["insurance_monthly"]),
                ("other_owner_costs_monthly", "Other owner costs ($/mo)", DEFAULTS["other_owner_costs_monthly"]),
            ],
        },
        {
            "title": "Growth & Returns",
            "fields": [
                ("home_appreciation", "Home appreciation (annual decimal)", DEFAULTS["home_appreciation"]),
                ("investment_return", "Investment return (annual decimal)", DEFAULTS["investment_return"]),
                ("inflation", "Inflation (annual decimal)", DEFAULTS["inflation"]),
                ("rent_growth", "Rent growth (annual decimal)", DEFAULTS["rent_growth"]),
                ("maintenance_growth", "Maintenance growth (annual decimal)", DEFAULTS["maintenance_growth"]),
                ("insurance_growth", "Insurance growth (annual decimal)", DEFAULTS["insurance_growth"]),
                (
                    "other_owner_costs_growth",
                    "Other owner costs growth (annual decimal)",
                    DEFAULTS["other_owner_costs_growth"],
                ),
                ("max_years", "Max horizon (years)", DEFAULTS["max_years"]),
            ],
        },
    ]

    # Convert dict to an object with attribute access for templating
    class AttrView(dict):
        __getattr__ = dict.get

    result_obj = AttrView(result) if result else None
    assumptions_obj = AttrView(result["assumptions"]) if result else None
    if result_obj:
        result_obj.assumptions = assumptions_obj

    return render_template_string(
        TEMPLATE,
        groups=groups,
        request=request,
        result=result_obj,
        error=error,
    )


if __name__ == "__main__":
    app.run(debug=True)
