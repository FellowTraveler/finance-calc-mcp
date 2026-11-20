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

## Use as an MCP Server

### Security update (0.2.1)

Version 0.2.1 replaces Python expression execution with a restricted math
interpreter, bounds calculation/output sizes, and updates vulnerable dependencies.
Older releases should be upgraded once 0.2.1 is published:

```bash
uv tool upgrade finance-calc-mcp
# or: pip install --upgrade 'finance-calc-mcp>=0.2.1'

# Refresh uvx's cached environment, including dependencies
uvx --upgrade 'finance-calc-mcp>=0.2.1' calc "185000 * 0.21"
```

For MCP configurations, use `uvx --upgrade 'finance-calc-mcp>=0.2.1'`
(JSON args: `["--upgrade", "finance-calc-mcp>=0.2.1"]`), then restart the client.
Until the release is published, maintainers can test this checkout with
`uv run --locked finance-calc-mcp`.

### Prerequisites

Install [uv](https://docs.astral.sh/uv/) if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal after installing, then confirm `uvx` works:

```bash
uvx --version
```

### Claude Desktop

Edit your Claude Desktop config:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**macOS:**

```json
{
  "mcpServers": {
    "finance-calculator": {
      "command": "/bin/bash",
      "args": ["-lc", "uvx finance-calc-mcp"]
    }
  }
}
```

> Claude Desktop on macOS is a GUI app that doesn't inherit your shell PATH.
> The `/bin/bash -lc` wrapper runs a login shell so `uvx` is found regardless
> of where `uv` was installed.

**Windows:**

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

Restart Claude Desktop. The finance tools will appear automatically.

### Claude Code (terminal)

```bash
claude mcp add finance-calculator -- uvx finance-calc-mcp
```

### Other MCP Clients

Any MCP-compatible client can launch the server:

```bash
uvx finance-calc-mcp
```

With no arguments, it starts in MCP server mode (stdio transport).

---

## MCP Tools

When connected as an MCP server, Claude gets these tools:

### `calculate`

Evaluate a financial/business math expression. Supports `+`, `-`, `*`, `/`, `**`, `%`, parentheses, and functions: `round()`, `abs()`, `max()`, `min()`, `sum()`, `sqrt()`, `log()`, `floor()`, `ceil()`, `pow()`.

Expressions may use `pi`, `e`, and numeric lists/tuples for aggregate functions
(for example, `sum([1, 2, 3])`). `pow()` accepts two arguments. Python attributes,
indexing, comprehensions, strings, and arbitrary function calls are rejected.
Expressions are limited to 4,096 characters, 256 syntax-tree nodes, and 32 nesting
levels; results and intermediate numbers must be finite real numbers.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `expression` | string | yes | Math expression to evaluate |

### `gross_margin`

Calculate gross margin, gross profit, and markup from revenue and COGS.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `revenue` | number | yes | Total revenue |
| `cogs` | number | yes | Cost of goods sold |

### `us_income_tax_estimate`

Estimate 2024 US federal income tax for individuals, with bracket-by-bracket detail.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `taxable_income` | number | yes | Taxable income in USD |
| `filing_status` | string | yes | `single`, `married_jointly`, `married_separately`, or `head_of_household` |

### `self_employment_tax`

Calculate self-employment (SE) tax and deductible half for Schedule SE. Covers Social Security, Medicare, and the additional Medicare surtax above $200k.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `net_self_employment_income` | number | yes | Net profit from self-employment |

### `depreciation`

Calculate a depreciation schedule (straight-line or double-declining balance).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `asset_cost` | number | yes | Asset purchase price |
| `useful_life` | integer | yes | Useful life in years (1–100) |
| `salvage_value` | number | no | Salvage/residual value (default 0) |
| `method` | string | no | `straight_line` (default) or `double_declining` |

### `payroll_summary`

Estimate employer payroll costs and employee net pay for a given gross salary. Covers FICA (Social Security + Medicare), FUTA, and SUTA.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `gross_annual_salary` | number | yes | Annual gross salary |
| `state_suta_rate` | number | no | State unemployment rate % (default 2.7) |

### `loan_amortization`

Generate a loan amortization summary: monthly payment, total interest paid, and optionally a full month-by-month schedule.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `principal` | number | yes | Loan principal |
| `annual_rate_pct` | number | yes | Annual interest rate as percent (e.g. 6.5) |
| `term_years` | integer | yes | Loan term in years (1–100) |
| `show_schedule` | boolean | no | Return full amortization table (default false) |

### `percent_change`

Calculate percent change between two values.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `old_value` | number | yes | Starting/original value |
| `new_value` | number | yes | Ending/new value |

### `break_even`

Calculate break-even units and revenue given fixed costs, price per unit, and variable cost per unit.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `fixed_costs` | number | yes | Total fixed costs |
| `price_per_unit` | number | yes | Selling price per unit |
| `variable_cost_per_unit` | number | yes | Variable cost per unit |

### `currency_format`

Format a number as a USD currency string.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `amount` | number | yes | Amount to format |
| `decimals` | integer | no | Decimal places, 0–20 (default 2) |

---

## CLI Usage

Every MCP tool is also available as a CLI command.

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

### Example Output

```
$ finance-calc-mcp tax 185000 single

2024 Federal Income Tax Estimate (single)
Taxable Income:   $185,000.00
Federal Tax:      $37,442.50
Effective Rate:   20.24%

Bracket Detail:
  10%  $0.00 – $11,600.00:  $11,600.00 taxed → $1,160.00
  12%  $11,600.00 – $47,150.00:  $35,550.00 taxed → $4,266.00
  22%  $47,150.00 – $100,525.00:  $53,375.00 taxed → $11,742.50
  24%  $100,525.00 – $191,950.00:  $84,475.00 taxed → $20,274.00
```

```
$ finance-calc-mcp amortize 400000 6.5 30

Loan Amortization Summary
Principal:       $400,000.00
Rate:            6.500% APR
Term:            30 years (360 months)
Monthly Payment: $2,528.27
Total Paid:      $910,177.52
Total Interest:  $510,177.52
Interest/Dollar: 127.54%
```

---

## License

MIT

## Development checks

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
uv export --locked --no-dev --no-emit-project -o /tmp/finance-calc-requirements.txt
uvx pip-audit -r /tmp/finance-calc-requirements.txt --no-deps --disable-pip
uv build
```

CI runs tests and dependency audits on Python 3.10 and 3.14 on pushes, pull
requests, and weekly. Dependabot checks the uv lockfile and GitHub Actions weekly.
Dependency security floors in `pyproject.toml` protect published installs;
`uv.lock` records the tested versions for source checkouts. Keep both updated.
The server uses stdio only; it does not expose an HTTP endpoint.

### Publishing a release

The `Publish to PyPI` workflow builds and audits a version tag, then publishes
the distributions using PyPI trusted publishing. Its publishing job uses the
GitHub environment `pypi`; no long-lived API token is needed.

Configure the project's PyPI trusted publisher with owner `FellowTraveler`,
repository `finance-calc-mcp`, workflow `publish.yml`, and environment `pypi`.
After CI passes, create and push a tag matching the package version, then run:

```bash
gh workflow run publish.yml -f tag=v0.2.1
```

Verify the workflow succeeds and the new version is available on PyPI before
announcing the release.
