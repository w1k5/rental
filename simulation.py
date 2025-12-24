from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any

# -----------------------------
# Helpers
# -----------------------------
def monthly_rate(annual_rate: float) -> float:
    return annual_rate / 12.0

def pmt(principal: float, annual_rate: float, months: int) -> float:
    """Monthly payment for an amortizing loan. Handles 0% safely."""
    if months <= 0:
        return 0.0
    r = monthly_rate(annual_rate)
    if abs(r) < 1e-12:
        return principal / months
    factor = (1 + r) ** months
    return principal * (r * factor) / (factor - 1)

def grow_monthly(value0: float, annual_growth: float, month_index: int) -> float:
    """Compound growth with annual rate, applied monthly (month_index starting at 0)."""
    return value0 * ((1 + annual_growth) ** (month_index / 12.0))

def selling_cost(value: float, sell_cost_pct: float) -> float:
    return value * sell_cost_pct

def closing_cost(value: float, close_cost_pct: float) -> float:
    return value * close_cost_pct

def deflator(inflation_annual: float, month_index: int) -> float:
    """Convert nominal dollars at time t to 'today' dollars (real)."""
    return (1 + inflation_annual) ** (month_index / 12.0)

# -----------------------------
# Inputs
# -----------------------------
@dataclass
class ScenarioParams:
    purchase_price: float
    down_payment: float  # dollars
    term_years: int

    # Rates (annual, nominal)
    home_appreciation: float      # e.g. 0.02
    investment_return: float      # e.g. 0.07
    inflation: float              # e.g. 0.03

    # Mortgage rates:
    # Provide either fixed_rate, OR a variable schedule as a list of (start_month, annual_rate).
    # Example: [(0, 0.065), (24, 0.075), (60, 0.06)]
    fixed_mortgage_rate: Optional[float] = None
    variable_rate_schedule: Optional[List[Tuple[int, float]]] = None

    # Monthly costs (month 0 nominal dollars)
    rent_monthly: float = 0.0
    maintenance_monthly: float = 0.0  # co-op maintenance
    insurance_monthly: float = 0.0
    other_owner_costs_monthly: float = 0.0  # optional: utilities delta, assessments, etc.

    # Growth on monthly costs
    rent_growth: float = 0.03
    maintenance_growth: float = 0.03
    insurance_growth: float = 0.03
    other_owner_costs_growth: float = 0.03

    # Transaction costs
    buy_closing_cost_pct: float = 0.02
    sell_cost_pct: float = 0.06

    # Horizon
    max_years: int = 30

    # If True, compare in real (inflation-adjusted) dollars when reporting break-even.
    report_real: bool = True

# -----------------------------
# Rate schedule logic
# -----------------------------
def rate_for_month(month: int, fixed_rate: Optional[float], schedule: Optional[List[Tuple[int, float]]]) -> float:
    if fixed_rate is not None:
        return fixed_rate
    if not schedule:
        raise ValueError("Provide either fixed_mortgage_rate or variable_rate_schedule.")
    # schedule is list of (start_month, rate). Use the last rate whose start_month <= month.
    schedule_sorted = sorted(schedule, key=lambda x: x[0])
    current = schedule_sorted[0][1]
    for start_m, r in schedule_sorted:
        if month >= start_m:
            current = r
        else:
            break
    return current

# -----------------------------
# Simulation
# -----------------------------
def simulate_break_even(params: ScenarioParams) -> Dict[str, Any]:
    P0 = params.purchase_price
    D = params.down_payment
    L0 = P0 - D
    if L0 < 0:
        raise ValueError("Down payment cannot exceed purchase price.")

    term_months = params.term_years * 12
    horizon_months = params.max_years * 12

    buy_close = closing_cost(P0, params.buy_closing_cost_pct)
    # Cash needed up front to buy (ignoring reserves etc.)
    upfront_buy_cash = D + buy_close

    # Portfolio balances
    port_rent = upfront_buy_cash  # if renting, you invest what you'd have used to buy
    port_buy = 0.0               # optional: if owning is cheaper than renting some months, invest the difference

    # Mortgage state
    balance = L0

    # Initial payment (will be recalculated if variable rates change)
    initial_rate = rate_for_month(0, params.fixed_mortgage_rate, params.variable_rate_schedule)
    payment = pmt(balance, initial_rate, term_months)

    # Track break-even
    break_even_month = None

    # Store a small history for debugging / optional inspection
    history = []

    last_rate = initial_rate

    for m in range(horizon_months + 1):
        # Update mortgage rate/payment if needed (variable)
        current_rate = rate_for_month(m, params.fixed_mortgage_rate, params.variable_rate_schedule)
        months_remaining = max(term_months - m, 0)

        if abs(current_rate - last_rate) > 1e-12:
            # Recast payment to amortize remaining balance over remaining months
            payment = pmt(balance, current_rate, months_remaining) if months_remaining > 0 else 0.0
            last_rate = current_rate

        # Evolve rents/costs (nominal)
        rent_t = grow_monthly(params.rent_monthly, params.rent_growth, m)

        maint_t = grow_monthly(params.maintenance_monthly, params.maintenance_growth, m)
        ins_t = grow_monthly(params.insurance_monthly, params.insurance_growth, m)
        other_t = grow_monthly(params.other_owner_costs_monthly, params.other_owner_costs_growth, m)

        # Mortgage payment / amortization for this month
        interest = 0.0
        principal_paid = 0.0
        if m < term_months and balance > 1e-8:
            r_m = monthly_rate(current_rate)
            interest = balance * r_m
            principal_paid = max(payment - interest, 0.0)
            principal_paid = min(principal_paid, balance)
            balance -= principal_paid

        # Owner monthly outflow (nominal)
        owner_outflow = (payment if m < term_months else 0.0) + maint_t + ins_t + other_t

        # Compare monthly cashflow difference:
        # If renting is cheaper, renter invests the difference.
        # If owning is cheaper, owner invests the difference.
        diff = owner_outflow - rent_t  # positive means owning costs more this month

        # Grow portfolios, then apply cashflow
        port_rent *= (1 + monthly_rate(params.investment_return))
        port_buy *= (1 + monthly_rate(params.investment_return))

        # Apply cashflows (invest/withdraw)
        port_rent += max(diff, 0.0) * 0.0  # placeholder to emphasize logic (see below)

        if diff > 0:
            # owning costs more => renter invests the extra they didn't spend
            port_rent += diff
        else:
            # renting costs more => owner invests the extra they didn't spend
            port_buy += (-diff)

        # Home value and liquidation equity if sold now (nominal)
        home_value = grow_monthly(P0, params.home_appreciation, m)
        net_sale_proceeds = home_value - selling_cost(home_value, params.sell_cost_pct)
        liquidation_equity = max(net_sale_proceeds - balance, 0.0)

        nw_buy = liquidation_equity + port_buy
        nw_rent = port_rent

        # Optionally convert to real dollars for comparison
        if params.report_real:
            d = deflator(params.inflation, m)
            nw_buy_cmp = nw_buy / d
            nw_rent_cmp = nw_rent / d
        else:
            nw_buy_cmp = nw_buy
            nw_rent_cmp = nw_rent

        if break_even_month is None and nw_buy_cmp >= nw_rent_cmp:
            break_even_month = m

        if m % 12 == 0 or (break_even_month == m):
            history.append({
                "month": m,
                "year": m / 12.0,
                "mortgage_rate": current_rate,
                "mortgage_balance": balance,
                "home_value": home_value,
                "owner_outflow": owner_outflow,
                "rent": rent_t,
                "nw_buy": nw_buy_cmp,
                "nw_rent": nw_rent_cmp,
            })

        # If we found break-even, you can stop early if you want
        # but keeping it running can be useful for later inspection.
        # We'll stop early to answer your question directly.
        if break_even_month is not None and m >= break_even_month:
            break

    return {
        "break_even_month": break_even_month,
        "break_even_years": (break_even_month / 12.0) if break_even_month is not None else None,
        "used_real_dollars": params.report_real,
        "history": history,
        "assumptions": {
            "upfront_buy_cash": upfront_buy_cash,
            "buy_closing_cost": buy_close,
            "sell_cost_pct": params.sell_cost_pct,
            "buy_closing_cost_pct": params.buy_closing_cost_pct,
        }
    }

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run buy-vs-rent break-even simulation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--purchase-price", type=float, default=1_200_000, help="dollars")
    parser.add_argument("--down-payment", type=float, default=240_000, help="dollars")
    parser.add_argument("--term-years", type=int, default=30, help="years")
    parser.add_argument("--home-appreciation", type=float, default=0.015, help="annual rate (decimal)")
    parser.add_argument("--investment-return", type=float, default=0.075, help="annual rate (decimal)")
    parser.add_argument("--inflation", type=float, default=0.03, help="annual rate (decimal)")
    parser.add_argument("--fixed-mortgage-rate", type=float, default=None, help="annual rate (decimal)")
    parser.add_argument(
        "--variable-rate-schedule",
        type=str,
        default="0:0.065,24:0.075,60:0.060",
        help="comma-separated start_month:annual_rate pairs",
    )
    parser.add_argument("--rent-monthly", type=float, default=5_500, help="dollars per month")
    parser.add_argument("--maintenance-monthly", type=float, default=2_200, help="dollars per month")
    parser.add_argument("--insurance-monthly", type=float, default=150, help="dollars per month")
    parser.add_argument("--other-owner-costs-monthly", type=float, default=150, help="dollars per month")
    parser.add_argument("--rent-growth", type=float, default=0.035, help="annual rate (decimal)")
    parser.add_argument("--maintenance-growth", type=float, default=0.035, help="annual rate (decimal)")
    parser.add_argument("--insurance-growth", type=float, default=0.03, help="annual rate (decimal)")
    parser.add_argument("--other-owner-costs-growth", type=float, default=0.03, help="annual rate (decimal)")
    parser.add_argument("--buy-closing-cost-pct", type=float, default=0.02, help="percent of price (decimal)")
    parser.add_argument("--sell-cost-pct", type=float, default=0.06, help="percent of price (decimal)")
    parser.add_argument("--max-years", type=int, default=30, help="years")
    report_group = parser.add_mutually_exclusive_group()
    report_group.add_argument(
        "--report-real",
        dest="report_real",
        action="store_true",
        default=True,
        help="compare in inflation-adjusted dollars",
    )
    report_group.add_argument(
        "--report-nominal",
        dest="report_real",
        action="store_false",
        help="compare in nominal dollars",
    )

    args = parser.parse_args()

    use_real = args.report_real

    variable_schedule = None
    if args.fixed_mortgage_rate is None:
        schedule = []
        if args.variable_rate_schedule:
            for item in args.variable_rate_schedule.split(","):
                item = item.strip()
                if not item:
                    continue
                start_str, rate_str = item.split(":")
                schedule.append((int(start_str), float(rate_str)))
        variable_schedule = schedule if schedule else None

    params = ScenarioParams(
        purchase_price=args.purchase_price,
        down_payment=args.down_payment,
        term_years=args.term_years,

        home_appreciation=args.home_appreciation,
        investment_return=args.investment_return,
        inflation=args.inflation,

        fixed_mortgage_rate=args.fixed_mortgage_rate,
        variable_rate_schedule=variable_schedule,

        rent_monthly=args.rent_monthly,
        maintenance_monthly=args.maintenance_monthly,
        insurance_monthly=args.insurance_monthly,
        other_owner_costs_monthly=args.other_owner_costs_monthly,

        rent_growth=args.rent_growth,
        maintenance_growth=args.maintenance_growth,
        insurance_growth=args.insurance_growth,
        other_owner_costs_growth=args.other_owner_costs_growth,

        buy_closing_cost_pct=args.buy_closing_cost_pct,
        sell_cost_pct=args.sell_cost_pct,

        max_years=args.max_years,
        report_real=use_real,
    )

    result = simulate_break_even(params)
    m = result["break_even_month"]
    y = result["break_even_years"]

    if m is None:
        print("No break-even found within the horizon.")
    else:
        print(f"Break-even at month {m} (~{y:.2f} years). "
              f"Compared in {'real' if result['used_real_dollars'] else 'nominal'} dollars.")

    # Optional: print a few checkpoints
    for row in result["history"][-5:]:
        print(row)
