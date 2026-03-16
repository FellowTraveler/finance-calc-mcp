#!/usr/bin/env python3
"""
Finance Calculator MCP Server + CLI
Business, financial, and tax calculations.
Usage:
  MCP server:  finance-calc-mcp
  CLI:         finance-calc-mcp calc "125000 * 0.21"
               finance-calc-mcp margin 850000 612000
               finance-calc-mcp tax 185000 single
               finance-calc-mcp depreciation 50000 5
               finance-calc-mcp payroll 95000
               finance-calc-mcp amortize 400000 6.5 30
"""

import sys
import math
import argparse
from typing import Any


# ── MCP imports (only needed in server mode) ──────────────────────────────────
def run_mcp_server():
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    import asyncio

    server = Server("finance-calculator")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="calculate",
                description=(
                    "Evaluate a financial/business math expression. "
                    "Supports +, -, *, /, **, %, parentheses, and common "
                    "functions: round(), abs(), max(), min(), sum(), sqrt(). "
                    "Examples: '125000 * 0.21', '(85000 - 12000) / 12', "
                    "'round(1234567.89, -3)'"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression to evaluate"}
                    },
                    "required": ["expression"]
                }
            ),
            Tool(
                name="gross_margin",
                description="Calculate gross margin, gross profit, and markup from revenue and COGS.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "revenue":  {"type": "number", "description": "Total revenue"},
                        "cogs":     {"type": "number", "description": "Cost of goods sold"}
                    },
                    "required": ["revenue", "cogs"]
                }
            ),
            Tool(
                name="us_income_tax_estimate",
                description=(
                    "Estimate 2024 US federal income tax (individuals). "
                    "Filing statuses: single, married_jointly, married_separately, head_of_household."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "taxable_income": {"type": "number", "description": "Taxable income in USD"},
                        "filing_status":  {"type": "string", "description": "single | married_jointly | married_separately | head_of_household"}
                    },
                    "required": ["taxable_income", "filing_status"]
                }
            ),
            Tool(
                name="self_employment_tax",
                description="Calculate self-employment (SE) tax and deductible half for Schedule SE.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "net_self_employment_income": {"type": "number", "description": "Net profit from self-employment"}
                    },
                    "required": ["net_self_employment_income"]
                }
            ),
            Tool(
                name="depreciation",
                description="Calculate straight-line or MACRS-style depreciation schedule.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_cost":    {"type": "number", "description": "Asset purchase price"},
                        "useful_life":   {"type": "number", "description": "Useful life in years"},
                        "salvage_value": {"type": "number", "description": "Salvage/residual value (default 0)", "default": 0},
                        "method":        {"type": "string",  "description": "straight_line | double_declining (default: straight_line)"}
                    },
                    "required": ["asset_cost", "useful_life"]
                }
            ),
            Tool(
                name="payroll_summary",
                description=(
                    "Estimate employer payroll costs and employee net pay for a given gross salary. "
                    "Covers FICA (SS + Medicare), FUTA, and SUTA estimate."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "gross_annual_salary": {"type": "number", "description": "Annual gross salary"},
                        "state_suta_rate":     {"type": "number", "description": "State unemployment rate % (default 2.7)", "default": 2.7}
                    },
                    "required": ["gross_annual_salary"]
                }
            ),
            Tool(
                name="loan_amortization",
                description="Generate a loan amortization summary (monthly payment, total interest, full schedule).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "principal":      {"type": "number", "description": "Loan principal"},
                        "annual_rate_pct":{"type": "number", "description": "Annual interest rate as percent (e.g. 6.5)"},
                        "term_years":     {"type": "number", "description": "Loan term in years"},
                        "show_schedule":  {"type": "boolean","description": "Return full amortization table (default false)"}
                    },
                    "required": ["principal", "annual_rate_pct", "term_years"]
                }
            ),
            Tool(
                name="percent_change",
                description="Calculate percent change, markup, or margin between two values.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "old_value": {"type": "number", "description": "Starting/original value"},
                        "new_value": {"type": "number", "description": "Ending/new value"}
                    },
                    "required": ["old_value", "new_value"]
                }
            ),
            Tool(
                name="break_even",
                description="Calculate break-even units and revenue given fixed costs, price per unit, and variable cost per unit.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "fixed_costs":         {"type": "number", "description": "Total fixed costs"},
                        "price_per_unit":      {"type": "number", "description": "Selling price per unit"},
                        "variable_cost_per_unit": {"type": "number", "description": "Variable cost per unit"}
                    },
                    "required": ["fixed_costs", "price_per_unit", "variable_cost_per_unit"]
                }
            ),
            Tool(
                name="currency_format",
                description="Format a number as USD currency string (or other locale).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "amount":   {"type": "number", "description": "Amount to format"},
                        "decimals": {"type": "integer","description": "Decimal places (default 2)"}
                    },
                    "required": ["amount"]
                }
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            result = dispatch(name, arguments)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_run())


# ── Core calculation logic (shared by MCP + CLI) ──────────────────────────────

def fmt(n: float, decimals: int = 2) -> str:
    """Format number with commas and fixed decimals."""
    return f"{n:,.{decimals}f}"


def safe_eval(expr: str) -> float:
    """Safely evaluate a math expression."""
    allowed = {
        "__builtins__": {},
        "round": round, "abs": abs, "max": max, "min": min,
        "sum": sum, "sqrt": math.sqrt, "log": math.log,
        "floor": math.floor, "ceil": math.ceil, "pow": pow,
        "pi": math.pi, "e": math.e,
    }
    try:
        result = eval(compile(expr, "<expr>", "eval"), allowed)  # noqa: S307
        return float(result)
    except Exception as exc:
        raise ValueError(f"Cannot evaluate '{expr}': {exc}") from exc


# 2024 US Federal Income Tax Brackets
TAX_BRACKETS = {
    "single": [
        (11600, 0.10), (47150, 0.12), (100525, 0.22),
        (191950, 0.24), (243725, 0.32), (609350, 0.35), (float("inf"), 0.37)
    ],
    "married_jointly": [
        (23200, 0.10), (94300, 0.12), (201050, 0.22),
        (383900, 0.24), (487450, 0.32), (731200, 0.35), (float("inf"), 0.37)
    ],
    "married_separately": [
        (11600, 0.10), (47150, 0.12), (100525, 0.22),
        (191950, 0.24), (243725, 0.32), (365600, 0.35), (float("inf"), 0.37)
    ],
    "head_of_household": [
        (16550, 0.10), (63100, 0.12), (100500, 0.22),
        (191950, 0.24), (243700, 0.32), (609350, 0.35), (float("inf"), 0.37)
    ],
}


def calc_federal_tax(income: float, status: str) -> dict:
    brackets = TAX_BRACKETS.get(status)
    if not brackets:
        raise ValueError(f"Unknown filing status: {status}. Use: {', '.join(TAX_BRACKETS)}")
    tax = 0.0
    prev = 0.0
    detail = []
    for ceiling, rate in brackets:
        if income <= prev:
            break
        taxable = min(income, ceiling) - prev
        bucket_tax = taxable * rate
        tax += bucket_tax
        detail.append({"bracket_top": ceiling, "rate_pct": rate * 100, "taxable": taxable, "tax": bucket_tax})
        prev = ceiling
    effective = (tax / income * 100) if income else 0
    return {"tax": tax, "effective_rate_pct": effective, "brackets": detail}


def dispatch(name: str, args: dict) -> str:
    if name == "calculate":
        expr = args["expression"]
        result = safe_eval(expr)
        return f"Result: {fmt(result)}\n(raw: {result})"

    elif name == "gross_margin":
        rev, cogs = float(args["revenue"]), float(args["cogs"])
        gross_profit = rev - cogs
        margin_pct = (gross_profit / rev * 100) if rev else 0
        markup_pct = (gross_profit / cogs * 100) if cogs else 0
        return (
            f"Gross Profit:   ${fmt(gross_profit)}\n"
            f"Gross Margin:   {fmt(margin_pct)}%\n"
            f"Markup:         {fmt(markup_pct)}%\n"
            f"Revenue:        ${fmt(rev)}\n"
            f"COGS:           ${fmt(cogs)}"
        )

    elif name == "us_income_tax_estimate":
        income = float(args["taxable_income"])
        status = args["filing_status"].lower().replace(" ", "_").replace("-", "_")
        r = calc_federal_tax(income, status)
        lines = [
            f"2024 Federal Income Tax Estimate ({status})",
            f"Taxable Income:   ${fmt(income)}",
            f"Federal Tax:      ${fmt(r['tax'])}",
            f"Effective Rate:   {fmt(r['effective_rate_pct'])}%",
            "",
            "Bracket Detail:"
        ]
        prev = 0
        for b in r["brackets"]:
            if b["taxable"] <= 0:
                continue
            top = f"${fmt(b['bracket_top'])}" if b["bracket_top"] != float("inf") else "∞"
            lines.append(f"  {fmt(b['rate_pct'],0)}%  ${fmt(prev)} – {top}:  ${fmt(b['taxable'])} taxed → ${fmt(b['tax'])}")
            prev = b["bracket_top"]
        return "\n".join(lines)

    elif name == "self_employment_tax":
        net = float(args["net_self_employment_income"])
        se_base = net * 0.9235
        ss_wage_base = 168600  # 2024
        ss_tax = min(se_base, ss_wage_base) * 0.124
        medicare_tax = se_base * 0.029
        # Additional Medicare surtax (>200k single)
        additional_medicare = max(0, se_base - 200000) * 0.009
        total_se = ss_tax + medicare_tax + additional_medicare
        deductible_half = total_se / 2
        return (
            f"Self-Employment Tax Summary\n"
            f"Net SE Income:         ${fmt(net)}\n"
            f"SE Wage Base (92.35%): ${fmt(se_base)}\n"
            f"Social Security Tax:   ${fmt(ss_tax)}\n"
            f"Medicare Tax:          ${fmt(medicare_tax)}\n"
            f"Add'l Medicare (>200k):${fmt(additional_medicare)}\n"
            f"─────────────────────────────\n"
            f"Total SE Tax:          ${fmt(total_se)}\n"
            f"Deductible Half:       ${fmt(deductible_half)}"
        )

    elif name == "depreciation":
        cost = float(args["asset_cost"])
        life = int(args["useful_life"])
        salvage = float(args.get("salvage_value", 0))
        method = args.get("method", "straight_line")
        depreciable = cost - salvage
        lines = [f"Depreciation Schedule ({method})", f"Asset Cost: ${fmt(cost)}, Life: {life} yrs, Salvage: ${fmt(salvage)}", ""]

        if method == "double_declining":
            rate = 2 / life
            book = cost
            for yr in range(1, life + 1):
                dep = min(book * rate, book - salvage)
                dep = max(dep, 0)
                book -= dep
                lines.append(f"Year {yr:>2}: Depreciation ${fmt(dep):>12}  Book Value ${fmt(book):>12}")
        else:
            annual = depreciable / life
            book = cost
            for yr in range(1, life + 1):
                book -= annual
                lines.append(f"Year {yr:>2}: Depreciation ${fmt(annual):>12}  Book Value ${fmt(book):>12}")

        lines.append(f"\nTotal Depreciated: ${fmt(depreciable)}")
        return "\n".join(lines)

    elif name == "payroll_summary":
        gross = float(args["gross_annual_salary"])
        suta_rate = float(args.get("state_suta_rate", 2.7)) / 100
        # Employee withholdings
        ss_ee = min(gross, 168600) * 0.062
        med_ee = gross * 0.0145
        add_med_ee = max(0, gross - 200000) * 0.009
        # Employer share
        ss_er = min(gross, 168600) * 0.062
        med_er = gross * 0.0145
        futa_er = min(gross, 7000) * 0.006   # net FUTA after credit
        suta_er = min(gross, 7000) * suta_rate
        total_er_cost = gross + ss_er + med_er + futa_er + suta_er
        employee_net_approx = gross - ss_ee - med_ee - add_med_ee
        return (
            f"Payroll Summary  (Gross: ${fmt(gross)})\n"
            f"\nEmployee Deductions (FICA only, pre-income-tax):\n"
            f"  Social Security (6.2%):    ${fmt(ss_ee)}\n"
            f"  Medicare (1.45%):          ${fmt(med_ee)}\n"
            f"  Add'l Medicare (>200k):    ${fmt(add_med_ee)}\n"
            f"  Est. Take-Home (pre-tax):  ${fmt(employee_net_approx)}\n"
            f"\nEmployer Costs:\n"
            f"  Gross Salary:              ${fmt(gross)}\n"
            f"  SS Match (6.2%):           ${fmt(ss_er)}\n"
            f"  Medicare Match (1.45%):    ${fmt(med_er)}\n"
            f"  FUTA (0.6% on $7k):        ${fmt(futa_er)}\n"
            f"  SUTA ({args.get('state_suta_rate',2.7)}% on $7k):        ${fmt(suta_er)}\n"
            f"  ─────────────────────────────\n"
            f"  Total Employer Cost:       ${fmt(total_er_cost)}"
        )

    elif name == "loan_amortization":
        principal = float(args["principal"])
        annual_rate = float(args["annual_rate_pct"]) / 100
        years = int(args["term_years"])
        show_schedule = args.get("show_schedule", False)
        monthly_rate = annual_rate / 12
        n = years * 12
        if monthly_rate == 0:
            payment = principal / n
        else:
            payment = principal * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
        total_paid = payment * n
        total_interest = total_paid - principal

        lines = [
            f"Loan Amortization Summary",
            f"Principal:       ${fmt(principal)}",
            f"Rate:            {fmt(annual_rate*100, 3)}% APR",
            f"Term:            {years} years ({n} months)",
            f"Monthly Payment: ${fmt(payment)}",
            f"Total Paid:      ${fmt(total_paid)}",
            f"Total Interest:  ${fmt(total_interest)}",
            f"Interest/Dollar: {fmt(total_interest/principal*100)}%",
        ]
        if show_schedule:
            lines += ["", f"{'Mo':>4}  {'Payment':>12}  {'Principal':>12}  {'Interest':>12}  {'Balance':>14}"]
            balance = principal
            for mo in range(1, n + 1):
                interest = balance * monthly_rate
                princ_pay = payment - interest
                balance -= princ_pay
                lines.append(f"{mo:>4}  ${fmt(payment):>11}  ${fmt(princ_pay):>11}  ${fmt(interest):>11}  ${fmt(max(balance,0)):>13}")
        return "\n".join(lines)

    elif name == "percent_change":
        old, new = float(args["old_value"]), float(args["new_value"])
        change = new - old
        pct = (change / old * 100) if old else float("inf")
        direction = "increase" if change >= 0 else "decrease"
        return (
            f"Old Value:      ${fmt(old)}\n"
            f"New Value:      ${fmt(new)}\n"
            f"Change:         ${fmt(change)}\n"
            f"Percent Change: {fmt(pct)}% {direction}"
        )

    elif name == "break_even":
        fixed = float(args["fixed_costs"])
        price = float(args["price_per_unit"])
        var = float(args["variable_cost_per_unit"])
        contrib_margin = price - var
        if contrib_margin <= 0:
            raise ValueError("Price per unit must exceed variable cost per unit.")
        be_units = fixed / contrib_margin
        be_revenue = be_units * price
        margin_ratio = contrib_margin / price * 100
        return (
            f"Break-Even Analysis\n"
            f"Fixed Costs:              ${fmt(fixed)}\n"
            f"Price/Unit:               ${fmt(price)}\n"
            f"Variable Cost/Unit:       ${fmt(var)}\n"
            f"Contribution Margin/Unit: ${fmt(contrib_margin)}\n"
            f"Contribution Margin Ratio:{fmt(margin_ratio)}%\n"
            f"─────────────────────────────\n"
            f"Break-Even Units:         {fmt(be_units)} units\n"
            f"Break-Even Revenue:       ${fmt(be_revenue)}"
        )

    elif name == "currency_format":
        amount = float(args["amount"])
        decimals = int(args.get("decimals", 2))
        return f"${fmt(amount, decimals)}"

    else:
        raise ValueError(f"Unknown tool: {name}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def cli():
    parser = argparse.ArgumentParser(
        prog="finance-calc-mcp",
        description="Business / Financial / Tax Calculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  calc <expression>                       Evaluate expression
  margin <revenue> <cogs>                 Gross margin
  tax <income> <filing_status>            US federal income tax estimate
  se-tax <net_income>                     Self-employment tax
  depreciation <cost> <years> [salvage]  Straight-line depreciation
  payroll <gross_salary> [suta_rate%]    Payroll cost summary
  amortize <principal> <rate%> <years>   Loan amortization
  pct-change <old> <new>                 Percent change
  break-even <fixed> <price> <var_cost>  Break-even analysis
  format <amount>                         Format as $currency

Examples:
  finance-calc-mcp calc "185000 * 0.21"
  finance-calc-mcp tax 185000 single
  finance-calc-mcp margin 850000 612000
  finance-calc-mcp amortize 400000 6.5 30
  finance-calc-mcp payroll 95000
  finance-calc-mcp depreciation 50000 5 5000
  finance-calc-mcp break-even 120000 49.99 18.50
"""
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("calc").add_argument("expression", nargs="+")

    p_margin = sub.add_parser("margin")
    p_margin.add_argument("revenue", type=float)
    p_margin.add_argument("cogs", type=float)

    p_tax = sub.add_parser("tax")
    p_tax.add_argument("income", type=float)
    p_tax.add_argument("filing_status")

    p_se = sub.add_parser("se-tax")
    p_se.add_argument("net_income", type=float)

    p_dep = sub.add_parser("depreciation")
    p_dep.add_argument("cost", type=float)
    p_dep.add_argument("years", type=int)
    p_dep.add_argument("salvage", type=float, nargs="?", default=0)
    p_dep.add_argument("--method", default="straight_line", choices=["straight_line", "double_declining"])

    p_pay = sub.add_parser("payroll")
    p_pay.add_argument("gross_salary", type=float)
    p_pay.add_argument("suta_rate", type=float, nargs="?", default=2.7)

    p_am = sub.add_parser("amortize")
    p_am.add_argument("principal", type=float)
    p_am.add_argument("rate", type=float)
    p_am.add_argument("years", type=int)
    p_am.add_argument("--schedule", action="store_true")

    p_pct = sub.add_parser("pct-change")
    p_pct.add_argument("old_value", type=float)
    p_pct.add_argument("new_value", type=float)

    p_be = sub.add_parser("break-even")
    p_be.add_argument("fixed_costs", type=float)
    p_be.add_argument("price_per_unit", type=float)
    p_be.add_argument("variable_cost_per_unit", type=float)

    p_fmt = sub.add_parser("format")
    p_fmt.add_argument("amount", type=float)
    p_fmt.add_argument("--decimals", type=int, default=2)

    args = parser.parse_args()

    cmd_map = {
        "calc":        lambda a: dispatch("calculate", {"expression": " ".join(a.expression)}),
        "margin":      lambda a: dispatch("gross_margin", {"revenue": a.revenue, "cogs": a.cogs}),
        "tax":         lambda a: dispatch("us_income_tax_estimate", {"taxable_income": a.income, "filing_status": a.filing_status}),
        "se-tax":      lambda a: dispatch("self_employment_tax", {"net_self_employment_income": a.net_income}),
        "depreciation":lambda a: dispatch("depreciation", {"asset_cost": a.cost, "useful_life": a.years, "salvage_value": a.salvage, "method": a.method}),
        "payroll":     lambda a: dispatch("payroll_summary", {"gross_annual_salary": a.gross_salary, "state_suta_rate": a.suta_rate}),
        "amortize":    lambda a: dispatch("loan_amortization", {"principal": a.principal, "annual_rate_pct": a.rate, "term_years": a.years, "show_schedule": a.schedule}),
        "pct-change":  lambda a: dispatch("percent_change", {"old_value": a.old_value, "new_value": a.new_value}),
        "break-even":  lambda a: dispatch("break_even", {"fixed_costs": a.fixed_costs, "price_per_unit": a.price_per_unit, "variable_cost_per_unit": a.variable_cost_per_unit}),
        "format":      lambda a: dispatch("currency_format", {"amount": a.amount, "decimals": a.decimals}),
    }

    if args.cmd in cmd_map:
        print(cmd_map[args.cmd](args))
    else:
        parser.print_help()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    """Entry point for both MCP server and CLI modes."""
    if len(sys.argv) == 1:
        run_mcp_server()
    else:
        cli()


if __name__ == "__main__":
    main()
