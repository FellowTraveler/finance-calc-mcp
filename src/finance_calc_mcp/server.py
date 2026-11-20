#!/usr/bin/env python3
"""Finance Calculator MCP server and CLI (shared calculation contracts)."""
import argparse
import importlib.metadata
import json
import sys

from .calculations import calculate_result, render_result
from .expressions import safe_eval as safe_eval  # Backward-compatible Python import.
from .schemas import DEFINITIONS, INPUT_SCHEMAS, OUTPUT_SCHEMA


def dispatch(name: str, args: dict) -> str:
    return render_result(calculate_result(name, args))


def run_mcp_server():
    import asyncio
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent, ToolAnnotations, CallToolResult

    server = Server(
        "finance-calculator", version=importlib.metadata.version("finance-calc-mcp"),
        instructions=(
            "Read-only financial calculations. Tax and payroll tools require an explicit tax_year "
            "(2024, 2025, or 2026). Ask for the year when unknown. Income-tax input is taxable "
            "income after deductions. Read the returned assumptions and sources. Monetary "
            "results are decimal strings in USD; undefined percentages are null."
        ),
    )

    @server.list_tools()
    async def list_tools():
        return [Tool(
            name=name, description=definition[0], inputSchema=INPUT_SCHEMAS[name],
            outputSchema=OUTPUT_SCHEMA,
            annotations=ToolAnnotations(title=name.replace('_', ' ').title(),
                readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        ) for name, definition in DEFINITIONS.items()]

    @server.call_tool()
    async def call_tool(name, arguments):
        try:
            payload = calculate_result(name, arguments)
            return ([TextContent(type="text", text=render_result(payload))], payload)
        except (ValueError, ArithmeticError) as exc:
            return CallToolResult(isError=True, content=[TextContent(type="text", text=f"Error: {exc}")])

    async def run():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(run())


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

Tax, se-tax, and payroll require --tax-year (2024, 2025, or 2026).
se-tax also requires --filing-status. Every command accepts --json.

Examples:
  finance-calc-mcp calc "185000 * 0.21"
  finance-calc-mcp tax 185000 single --tax-year 2026
  finance-calc-mcp margin 850000 612000
  finance-calc-mcp amortize 400000 6.5 30
  finance-calc-mcp payroll 95000 --tax-year 2026
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

    for tax_parser in (p_tax, p_se, p_pay):
        tax_parser.add_argument("--tax-year", type=int, required=True, choices=[2024, 2025, 2026])
    p_se.add_argument("--filing-status", required=True, choices=["single", "married_jointly", "married_separately", "head_of_household"])
    p_se.add_argument("--social-security-wages", type=float, default=0)
    p_se.add_argument("--medicare-wages", type=float, default=0,
                      help="Include both spouses' Medicare wages for a joint return")
    p_se.add_argument("--spouse-net-self-employment-income", type=float, default=0)
    p_pay.add_argument("--state-suta-wage-base", type=float, default=7000)
    p_pay.add_argument("--futa-credit-pct", type=float, default=5.4)
    for child in sub.choices.values():
        child.add_argument("--json", action="store_true", help="Return structured JSON instead of text")

    args = parser.parse_args()

    def output(name, values):
        payload = calculate_result(name, values)
        return json.dumps(payload, indent=2, allow_nan=False) if args.json else render_result(payload)

    cmd_map = {
        "calc":        lambda a: output("calculate", {"expression": " ".join(a.expression)}),
        "margin":      lambda a: output("gross_margin", {"revenue": a.revenue, "cogs": a.cogs}),
        "tax":         lambda a: output("us_income_tax_estimate", {"taxable_income": a.income, "filing_status": a.filing_status, "tax_year": a.tax_year}),
        "se-tax":      lambda a: output("self_employment_tax", {"net_self_employment_income": a.net_income, "tax_year": a.tax_year, "filing_status": a.filing_status, "social_security_wages": a.social_security_wages, "medicare_wages": a.medicare_wages, "spouse_net_self_employment_income": a.spouse_net_self_employment_income}),
        "depreciation":lambda a: output("depreciation", {"asset_cost": a.cost, "useful_life": a.years, "salvage_value": a.salvage, "method": a.method}),
        "payroll":     lambda a: output("payroll_summary", {"gross_annual_salary": a.gross_salary, "state_suta_rate": a.suta_rate, "tax_year": a.tax_year, "state_suta_wage_base": a.state_suta_wage_base, "futa_credit_pct": a.futa_credit_pct}),
        "amortize":    lambda a: output("loan_amortization", {"principal": a.principal, "annual_rate_pct": a.rate, "term_years": a.years, "show_schedule": a.schedule}),
        "pct-change":  lambda a: output("percent_change", {"old_value": a.old_value, "new_value": a.new_value}),
        "break-even":  lambda a: output("break_even", {"fixed_costs": a.fixed_costs, "price_per_unit": a.price_per_unit, "variable_cost_per_unit": a.variable_cost_per_unit}),
        "format":      lambda a: output("currency_format", {"amount": a.amount, "decimals": a.decimals}),
    }

    if args.cmd in cmd_map:
        try:
            print(cmd_map[args.cmd](args))
        except (ValueError, ArithmeticError) as exc:
            parser.error(str(exc))
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
