# finance-calc-mcp

Business, financial, and tax calculator — MCP server + CLI.

Single command install. No cloning required.

---

## Install

```bash
# Run directly (no install needed)
uvx finance-calc-mcp calc "185000 * 0.21"

# Or install permanently
uv tool install finance-calc-mcp
# or: pip install finance-calc-mcp
```

---

## Claude Desktop — MCP Config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "finance-calculator": {
      "command": "uvx",
      "args": ["finance-calc-mcp"]
    }
  }
}
```

Restart Claude Desktop.

---

## Claude Code — MCP Config

```bash
claude mcp add finance-calculator -- uvx finance-calc-mcp
```

---

## CLI Usage

```bash
# Evaluate any expression
finance-calc-mcp calc "185000 * 0.21"
finance-calc-mcp calc "(850000 - 612000) / 850000 * 100"

# Gross margin
finance-calc-mcp margin 850000 612000

# 2024 US federal income tax estimate
finance-calc-mcp tax 185000 single
finance-calc-mcp tax 320000 married_jointly

# Self-employment tax
finance-calc-mcp se-tax 95000

# Loan amortization (add --schedule for full table)
finance-calc-mcp amortize 400000 6.5 30
finance-calc-mcp amortize 400000 6.5 30 --schedule

# Payroll (optional: state SUTA rate %)
finance-calc-mcp payroll 95000
finance-calc-mcp payroll 95000 3.4

# Depreciation (straight-line default, or double_declining)
finance-calc-mcp depreciation 50000 5
finance-calc-mcp depreciation 50000 5 5000 --method double_declining

# Break-even analysis
finance-calc-mcp break-even 120000 49.99 18.50

# Percent change
finance-calc-mcp pct-change 1200000 1485000

# Format as currency
finance-calc-mcp format 1234567.89
```

---

## MCP Tools Available to Claude

| Tool | Description |
|---|---|
| `calculate` | Safe eval of any math expression |
| `gross_margin` | Revenue, COGS → profit, margin %, markup % |
| `us_income_tax_estimate` | 2024 federal tax with bracket detail |
| `self_employment_tax` | SE tax + deductible half |
| `depreciation` | Straight-line or double-declining schedule |
| `payroll_summary` | Employer cost + employee FICA |
| `loan_amortization` | Monthly payment, total interest, optional full schedule |
| `percent_change` | % change between two values |
| `break_even` | Units + revenue to break even |
| `currency_format` | Format number as $USD |

---

## License

MIT
