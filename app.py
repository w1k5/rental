"""Minimal browser UI to run the buy-vs-rent simulation."""
from __future__ import annotations

from typing import Dict, Optional

from flask import Flask, Response, render_template, request

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


def _float_from_form(form, name: str, default: float, errors: dict[str, str]) -> float:
    raw = form.get(name, "")
    if raw is None or raw == "":
        errors[name] = "Required."
        return float(default)
    try:
        return float(raw)
    except ValueError:
        errors[name] = "Must be a number."
        return float(default)


def _int_from_form(form, name: str, default: int, errors: dict[str, str]) -> int:
    raw = form.get(name, "")
    if raw is None or raw == "":
        errors[name] = "Required."
        return int(default)
    try:
        float_value = float(raw)
    except ValueError:
        errors[name] = "Must be a whole number."
        return int(default)
    if abs(float_value - round(float_value)) > 1e-9:
        errors[name] = "Must be a whole number."
        return int(default)
    return int(round(float_value))


def form_to_params(form) -> tuple[ScenarioParams, dict[str, str]]:
    errors: dict[str, str] = {}
    rate_mode = form.get("rate_mode", "variable")
    fixed = None
    variable_schedule = None

    if rate_mode == "fixed":
        fixed_rate = form.get("fixed_mortgage_rate")
        if fixed_rate:
            try:
                fixed = float(fixed_rate)
            except ValueError:
                errors["fixed_mortgage_rate"] = "Must be a number."
                fixed = None
        else:
            errors["fixed_mortgage_rate"] = "Required when Mortgage Rate mode is Fixed."
    else:
        raw_schedule = form.get("variable_rate_schedule", "")
        if not raw_schedule.strip():
            errors["variable_rate_schedule"] = "Required when Mortgage Rate mode is Variable."
            raw_schedule = "0:0.065,24:0.075,60:0.060"
        try:
            variable_schedule = parse_variable_schedule(raw_schedule)
        except Exception:  # noqa: BLE001
            errors["variable_rate_schedule"] = (
                "Use comma-separated start_month:annual_rate pairs (e.g., 0:0.065,24:0.075)."
            )
            variable_schedule = None

    purchase_price = _float_from_form(form, "purchase_price", DEFAULTS["purchase_price"], errors)
    down_payment = _float_from_form(form, "down_payment", DEFAULTS["down_payment"], errors)
    term_years = _int_from_form(form, "term_years", int(DEFAULTS["term_years"]), errors)
    max_years = _int_from_form(form, "max_years", int(DEFAULTS["max_years"]), errors)

    buy_closing_cost_pct = _float_from_form(form, "buy_closing_cost_pct", DEFAULTS["buy_closing_cost_pct"], errors)
    sell_cost_pct = _float_from_form(form, "sell_cost_pct", DEFAULTS["sell_cost_pct"], errors)
    if not (0.0 <= buy_closing_cost_pct <= 1.0):
        errors["buy_closing_cost_pct"] = "Must be between 0 and 1."
    if not (0.0 <= sell_cost_pct <= 1.0):
        errors["sell_cost_pct"] = "Must be between 0 and 1."

    if purchase_price <= 0:
        errors["purchase_price"] = "Must be greater than 0."
    if down_payment < 0:
        errors["down_payment"] = "Must be at least 0."
    if term_years <= 0:
        errors["term_years"] = "Must be at least 1."
    if max_years <= 0:
        errors["max_years"] = "Must be at least 1."

    params = ScenarioParams(
        purchase_price=purchase_price,
        down_payment=down_payment,
        term_years=term_years,
        home_appreciation=_float_from_form(form, "home_appreciation", DEFAULTS["home_appreciation"], errors),
        investment_return=_float_from_form(form, "investment_return", DEFAULTS["investment_return"], errors),
        inflation=_float_from_form(form, "inflation", DEFAULTS["inflation"], errors),
        fixed_mortgage_rate=fixed,
        variable_rate_schedule=variable_schedule,
        rent_monthly=_float_from_form(form, "rent_monthly", DEFAULTS["rent_monthly"], errors),
        maintenance_monthly=_float_from_form(form, "maintenance_monthly", DEFAULTS["maintenance_monthly"], errors),
        insurance_monthly=_float_from_form(form, "insurance_monthly", DEFAULTS["insurance_monthly"], errors),
        other_owner_costs_monthly=_float_from_form(
            form,
            "other_owner_costs_monthly",
            DEFAULTS["other_owner_costs_monthly"],
            errors,
        ),
        rent_growth=_float_from_form(form, "rent_growth", DEFAULTS["rent_growth"], errors),
        maintenance_growth=_float_from_form(form, "maintenance_growth", DEFAULTS["maintenance_growth"], errors),
        insurance_growth=_float_from_form(form, "insurance_growth", DEFAULTS["insurance_growth"], errors),
        other_owner_costs_growth=_float_from_form(
            form,
            "other_owner_costs_growth",
            DEFAULTS["other_owner_costs_growth"],
            errors,
        ),
        buy_closing_cost_pct=buy_closing_cost_pct,
        sell_cost_pct=sell_cost_pct,
        max_years=max_years,
        report_real=form.get("report_mode", "real") == "real",
    )
    return params, errors


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    field_errors: dict[str, str] = {}
    if request.method == "POST":
        try:
            params, field_errors = form_to_params(request.form)
            if field_errors:
                error = "Fix the highlighted fields and try again."
            else:
                result = simulate_break_even(params)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "Down payment cannot exceed purchase price" in msg:
                field_errors["down_payment"] = msg
            else:
                error = msg

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

    return render_template(
        "index.html",
        groups=groups,
        result=result_obj,
        error=error,
        field_errors=field_errors,
        breakeven_row=breakeven_row,
        checkpoints=checkpoints,
    )


@app.get("/og.svg")
def og_image() -> Response:
    title = "Buy vs Rent Simulator"
    subtitle = "Month-by-month break-even • Variable/Fixed rates • Real vs nominal"
    url = request.url_root.rstrip("/")
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f2f8f"/>
      <stop offset="100%" stop-color="#1652f0"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="10" stdDeviation="18" flood-color="#000" flood-opacity="0.25"/>
    </filter>
  </defs>

  <rect width="1200" height="630" fill="url(#bg)"/>

  <g filter="url(#shadow)">
    <rect x="70" y="70" width="1060" height="490" rx="28" fill="rgba(255,255,255,0.12)"/>
  </g>

  <g fill="#ffffff" opacity="0.92">
    <rect x="120" y="360" width="70" height="160" rx="6"/>
    <rect x="210" y="300" width="90" height="220" rx="6"/>
    <rect x="320" y="250" width="80" height="270" rx="6"/>
    <rect x="420" y="320" width="110" height="200" rx="6"/>
    <rect x="550" y="280" width="75" height="240" rx="6"/>
    <rect x="645" y="340" width="130" height="180" rx="6"/>
  </g>

  <g fill="#1652f0" opacity="0.95">
    <circle cx="165" cy="395" r="5"/>
    <circle cx="165" cy="415" r="5"/>
    <circle cx="165" cy="435" r="5"/>
    <circle cx="165" cy="455" r="5"/>

    <circle cx="250" cy="340" r="5"/>
    <circle cx="250" cy="360" r="5"/>
    <circle cx="250" cy="380" r="5"/>
    <circle cx="250" cy="400" r="5"/>

    <circle cx="360" cy="290" r="5"/>
    <circle cx="360" cy="310" r="5"/>
    <circle cx="360" cy="330" r="5"/>
    <circle cx="360" cy="350" r="5"/>

    <circle cx="470" cy="360" r="5"/>
    <circle cx="470" cy="380" r="5"/>
    <circle cx="470" cy="400" r="5"/>
    <circle cx="470" cy="420" r="5"/>

    <circle cx="587" cy="320" r="5"/>
    <circle cx="587" cy="340" r="5"/>
    <circle cx="587" cy="360" r="5"/>
    <circle cx="587" cy="380" r="5"/>

    <circle cx="710" cy="375" r="5"/>
    <circle cx="710" cy="395" r="5"/>
    <circle cx="710" cy="415" r="5"/>
    <circle cx="710" cy="435" r="5"/>
  </g>

  <text x="120" y="200" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial"
        font-size="68" font-weight="800" fill="#ffffff">{title}</text>
  <text x="120" y="260" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial"
        font-size="30" font-weight="600" fill="rgba(255,255,255,0.90)">{subtitle}</text>

  <g>
    <rect x="120" y="300" width="520" height="64" rx="14" fill="rgba(0,0,0,0.16)"/>
    <text x="148" y="343" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
          font-size="24" font-weight="700" fill="#ffffff">{url}</text>
  </g>

  <g transform="translate(825, 165)" filter="url(#shadow)">
    <rect width="280" height="160" rx="22" fill="rgba(255,255,255,0.16)"/>
    <path d="M40 120 L90 75 L140 105 L190 55 L240 80" fill="none" stroke="#ffffff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="90" cy="75" r="8" fill="#ffffff"/>
    <circle cx="140" cy="105" r="8" fill="#ffffff"/>
    <circle cx="190" cy="55" r="8" fill="#ffffff"/>
    <circle cx="240" cy="80" r="8" fill="#ffffff"/>
    <text x="40" y="52" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial"
          font-size="20" font-weight="800" fill="#ffffff">Break-even</text>
  </g>
</svg>
"""

    resp = Response(svg, mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


if __name__ == "__main__":
    app.run(debug=True)
