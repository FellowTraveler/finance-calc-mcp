import asyncio
import math
import subprocess
import sys
import unittest
import json

from jsonschema import validate

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from finance_calc_mcp.server import dispatch, safe_eval
from finance_calc_mcp.calculations import calculate_result


EXAMPLES = {
    "calculate": {"expression": "185000 * 0.21"},
    "gross_margin": {"revenue": 850000, "cogs": 612000},
    "us_income_tax_estimate": {"taxable_income": 185000, "filing_status": "single", "tax_year": 2024},
    "self_employment_tax": {"net_self_employment_income": 95000, "tax_year": 2026, "filing_status": "single"},
    "depreciation": {"asset_cost": 50000, "useful_life": 5},
    "payroll_summary": {"gross_annual_salary": 95000, "tax_year": 2026},
    "loan_amortization": {"principal": 400000, "annual_rate_pct": 6.5, "term_years": 30},
    "percent_change": {"old_value": 1200000, "new_value": 1485000},
    "break_even": {"fixed_costs": 120000, "price_per_unit": 49.99, "variable_cost_per_unit": 18.50},
    "currency_format": {"amount": 1234567.89},
}


class ExpressionTests(unittest.TestCase):
    def test_documented_math(self):
        examples = {
            "185000 * 0.21": 38850,
            "(850000 - 612000) / 850000 * 100": 28,
            "round(1234567.89, -3)": 1235000,
            "abs(-3) + max(1, 2) + min([4, 5])": 9,
            "sum([1, 2, 3]) + sum((4, 5))": 15,
            "sqrt(16) + log(e) + floor(1.9) + ceil(1.1)": 8,
            "pow(2, 3) + 2**3 + 5%2": 17,
            "-2**2 + +3": -1,
            "pi": math.pi,
        }
        for expression, expected in examples.items():
            with self.subTest(expression=expression):
                self.assertAlmostEqual(safe_eval(expression), expected)

    def test_reject_python_and_resource_exhaustion(self):
        expressions = [
            "().__class__.__base__.__subclasses__()",
            "[c for c in ().__class__.__base__.__subclasses__()]",
            "__import__('os').getcwd()", "(lambda: 1)()", "[1][0]",
            "'x' * 1000000000", "[0] * 1000000000", "sum([0] * 1000000000)",
            "2**1000000000", "pow(2, 1000000000)", "9**9**9",
            "True", "1j", "1e999", "1 / 0", "sqrt(-1)", "[1, 2]",
            "sum([[1], [2]])", "round(1, ndigits=2)",
            "1+" * 200 + "1", "-" * 50 + "1", "1" * 4097,
        ]
        for expression in expressions:
            with self.subTest(expression=expression[:80]):
                self.assertRaises(ValueError, safe_eval, expression)

    def test_bounded_outputs(self):
        for tool, field, values in [
            ("depreciation", "useful_life", [0, -1, 1.5, 101, 10**20, True, float("inf")]),
            ("loan_amortization", "term_years", [0, -1, 1.5, 101, 10**20, float("nan")]),
            ("currency_format", "decimals", [-1, 1.5, 21, 10**20, True]),
        ]:
            for value in values:
                with self.subTest(tool=tool, value=value):
                    self.assertRaises(ValueError, dispatch, tool, {**EXAMPLES[tool], field: value})
        self.assertIn("Year 100:", dispatch("depreciation", {**EXAMPLES["depreciation"], "useful_life": 100}))
        self.assertIn("1200", dispatch("loan_amortization", {**EXAMPLES["loan_amortization"], "term_years": 100, "show_schedule": True}))
        self.assertEqual(dispatch("currency_format", {"amount": 1, "decimals": 20}), "$1.00000000000000000000")

    def test_cli(self):
        result = subprocess.run(
            [sys.executable, "-m", "finance_calc_mcp.server", "calc", "185000 * 0.21"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("38,850.00", result.stdout)


class MCPTests(unittest.TestCase):
    def test_stdio_tools_and_errors(self):
        async def exercise():
            params = StdioServerParameters(command=sys.executable, args=["-m", "finance_calc_mcp.server"])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self.assertEqual(init.serverInfo.name, "finance-calculator")
                    self.assertNotEqual(init.protocolVersion, "2024-11-05")
                    tools = await session.list_tools()
                    self.assertEqual({tool.name for tool in tools.tools}, set(EXAMPLES))
                    schemas = {tool.name: tool.outputSchema for tool in tools.tools}
                    for name, arguments in EXAMPLES.items():
                        result = await session.call_tool(name, arguments)
                        self.assertFalse(result.isError, result)
                        self.assertTrue(result.content)
                        self.assertEqual(result.structuredContent, calculate_result(name, arguments))
                        validate(result.structuredContent, schemas[name])
                        json.dumps(result.structuredContent, allow_nan=False)
                    for name, arguments in [
                        ("self_employment_tax", {**EXAMPLES["self_employment_tax"],
                            "filing_status": "married_jointly", "medicare_wages": 200000,
                            "spouse_net_self_employment_income": 50000}),
                        ("payroll_summary", {**EXAMPLES["payroll_summary"], "state_suta_wage_base": 15000,
                            "state_suta_rate": 3.4, "futa_credit_pct": 5.1}),
                        ("loan_amortization", {**EXAMPLES["loan_amortization"], "show_schedule": True}),
                        ("percent_change", {"old_value": 0, "new_value": 100}),
                    ]:
                        result = await session.call_tool(name, arguments)
                        self.assertFalse(result.isError, result)
                        self.assertEqual(result.structuredContent, calculate_result(name, arguments))
                        validate(result.structuredContent, schemas[name])
                    for name, arguments in [
                        ("calculate", {"expression": "().__class__.__base__.__subclasses__()"}),
                        ("calculate", {"expression": "2**1000000000"}),
                        ("calculate", {}),
                        ("currency_format", {"amount": 1, "decimals": 1000000000}),
                        ("depreciation", {"asset_cost": 1, "useful_life": 1000000000}),
                        ("loan_amortization", {**EXAMPLES["loan_amortization"], "term_years": 1000000000}),
                        ("us_income_tax_estimate", {"taxable_income": 100, "filing_status": "single"}),
                        ("self_employment_tax", {"net_self_employment_income": 95000, "tax_year": 2026}),
                        ("payroll_summary", {"gross_annual_salary": 100, "tax_year": 2027}),
                        ("gross_margin", {"revenue": 100, "cogs": 10, "unexpected": 1}),
                    ]:
                        result = await session.call_tool(name, arguments)
                        self.assertTrue(result.isError, result)
                    result = await session.call_tool("calculate", {"expression": "2+2"})
                    self.assertFalse(result.isError)
                    self.assertIn("4.00", result.content[0].text)

        asyncio.run(asyncio.wait_for(exercise(), timeout=30))

    def test_legacy_protocol_still_receives_readable_text(self):
        async def exercise():
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "finance_calc_mcp.server",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            async def send(message, reply=True):
                process.stdin.write((json.dumps(message) + "\n").encode())
                await process.stdin.drain()
                if reply:
                    return json.loads(await asyncio.wait_for(process.stdout.readline(), timeout=10))

            try:
                init = await send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "legacy-test", "version": "1.0"},
                }})
                self.assertEqual(init["result"]["protocolVersion"], "2024-11-05")
                await send({"jsonrpc": "2.0", "method": "notifications/initialized"}, reply=False)
                response = await send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                    "name": "us_income_tax_estimate", "arguments": EXAMPLES["us_income_tax_estimate"],
                }})
                self.assertFalse(response["result"].get("isError", False))
                self.assertIn("37,442.50", response["result"]["content"][0]["text"])
                self.assertIn("2024", response["result"]["content"][0]["text"])
            finally:
                process.stdin.close()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

        asyncio.run(asyncio.wait_for(exercise(), timeout=30))


if __name__ == "__main__":
    unittest.main()
