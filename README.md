# finance-calc-mcp

Local business and financial calculator: ten read-only MCP tools, also available
as CLI commands. No bank connections, market-data requests, or stored financial
records. Requires Python 3.10+ and an MCP client that can launch stdio servers.

## Install and run

```bash
# Run without a permanent installation (uv must be installed)
uvx --upgrade 'finance-calc-mcp>=0.3.0' calc '185000 * 0.21'

# Or install / upgrade a persistent command
uv tool install finance-calc-mcp
uv tool upgrade finance-calc-mcp
# Alternative: pip install --upgrade finance-calc-mcp
```

Install uv from its [official instructions](https://docs.astral.sh/uv/getting-started/installation/).

## Connect an MCP client

Configure your client's local MCP server command as `uvx`, with arguments
`["--upgrade", "finance-calc-mcp>=0.3.0"]`. For clients using JSON configuration:

```json
{
  "mcpServers": {
    "finance-calculator": {
      "command": "uvx",
      "args": ["--upgrade", "finance-calc-mcp>=0.3.0"]
    }
  }
}
```

If a desktop app cannot find `uvx`, replace `command` with the absolute path
reported by `command -v uvx` (macOS/Linux) or `where uvx` (Windows). Restart the
client after configuring or upgrading it. No arguments starts the stdio server;
there is no HTTP listener.

For Claude Code:

```bash
claude mcp add finance-calculator -- uvx --upgrade 'finance-calc-mcp>=0.3.0'
```

Example prompts:

- “Revenue is $850,000 and COGS is $612,000. Calculate margin and markup.”
- “Compare a $400,000 loan at 6.5% over 15 and 30 years.”
- “Estimate 2026 ordinary federal income tax on $185,000 of taxable income,
  filing single. Show the assumptions.”

The assistant receives both readable text and structured results. Values passed
through an AI client are also handled by that client and its provider.

## Migrating from 0.2.x to 0.3.0

- **Tax and payroll calls now require `tax_year`**: 2024, 2025, or 2026. CLI commands
  require `--tax-year`. There is no clock-dependent default or fallback for an
  unsupported year, including 2027.
- **Self-employment tax requires `filing_status`** (CLI `--filing-status`). Regular
  individual SE tax and return-level Additional Medicare Tax are separate results.
  Do not interpret the regular SE tax as the complete tax on all income.
- The double-declining depreciation method now switches to straight line when
  appropriate and reconciles to salvage. It is book depreciation, not MACRS.
- Loan totals sum rounded actual payments; the final payment may differ from the
  regular monthly payment. This can change totals from earlier unrounded estimates.
- Undefined percentages are `null` in structured output and `undefined` in text.
- Numeric inputs must be finite; invalid or unknown arguments return errors.
  Financial inputs are bounded to magnitude $1 trillion (general math expressions
  have separate limits). Existing tool names and CLI command names remain available.
- The SDK now negotiates protocol versions normally. Modern clients receive
  structured content; readable text remains available to older clients.

## Tools and inputs

Amounts are USD. Unless noted, monetary inputs must be nonnegative. Filing status
is `single`, `married_jointly`, `married_separately`, or `head_of_household`.
Qualifying surviving spouse is not currently a supported input status.

| Tool | Required inputs | Optional inputs |
|---|---|---|
| `calculate` | `expression` | — |
| `gross_margin` | `revenue`, `cogs` | — |
| `us_income_tax_estimate` | `taxable_income`, `filing_status`, `tax_year` | — |
| `self_employment_tax` | `net_self_employment_income`, `filing_status`, `tax_year` | `social_security_wages=0`, `medicare_wages=0`, `spouse_net_self_employment_income=0` |
| `payroll_summary` | `gross_annual_salary`, `tax_year` | `state_suta_rate=2.7`, `state_suta_wage_base=7000`, `futa_credit_pct=5.4` |
| `depreciation` | `asset_cost`, `useful_life` | `salvage_value=0`, `method="straight_line"` |
| `loan_amortization` | `principal`, `annual_rate_pct`, `term_years` | `show_schedule=false` |
| `percent_change` | `old_value`, `new_value` | — |
| `break_even` | `fixed_costs`, `price_per_unit`, `variable_cost_per_unit` | — |
| `currency_format` | `amount` | `decimals=2` |

### Tax estimates

`us_income_tax_estimate` applies ordinary-income rate schedules to **taxable
income after deductions**, before credits. It does not compute deductions, QBI,
credits, capital-gain rates, AMT, NIIT, or state taxes. It uses rate schedules rather
than the IRS tax-table income bands used for some returns. It returns bracket
amounts, tax, effective rate, selected year, assumptions, and source URLs.

`self_employment_tax` uses the normal Schedule SE method. Profit/loss is combined
for this individual; negative net profit produces zero taxable SE earnings. The
$400 minimum applies after the 92.35% adjustment. It excludes optional methods,
church employee rules, and special exemptions.

- `social_security_wages`: this individual's Social Security wages/tips, reducing
  the remaining annual cap. Do not include spouse wages.
- `medicare_wages`: total Medicare wages for the return, **including both spouses
  for married filing jointly**. Supply independently of Social Security wages.
- `spouse_net_self_employment_income`: spouse net business profit/loss, allowed
  only for joint returns. Each spouse's earnings threshold is applied separately;
  a loss by one spouse does not offset the other's SE earnings.
- `regular_self_employment_tax` and `deductible_half` concern this individual only.
  Spouse regular SE tax is excluded. Additional Medicare Tax is reported separately
  for wages and combined SE earnings at the return level, before withholding
  credits. Additional Medicare Tax is excluded from the deductible half.

Tax data is reviewed and versioned locally; there are no live tax lookups during
calculations. See [tax sources and annual review procedure](TAX_DATA.md).

### Payroll estimates

`payroll_summary` models one employee at one employer over a full calendar year,
assuming the supplied salary is taxable for all modeled taxes. It reports FICA
withholding, **pay after FICA before income tax and other deductions**, and employer
costs. It excludes income-tax withholding, benefits, and other deductions.

Additional Medicare **withholding** starts at $200,000 regardless of filing status;
this is not the employee's final return-level tax liability and has no employer
match. SUTA rate and wage base are explicit user assumptions, not state-specific
data. The default FUTA credit is 5.4 percentage points, assuming full eligibility;
set `futa_credit_pct` to the actual allowable credit, including reductions.

### Schedules, arithmetic, and rounding

Financial calculations use decimal arithmetic. Monetary inputs and tax/schedule
line items round to cents using **ROUND_HALF_UP**. Totals sum the rounded line
items. Percentages and fractional break-even units display four decimal places.
Structured decimal values are strings to preserve precision; counts are integers.

Loans use a fixed nominal annual percentage rate divided by 12, monthly payments
in arrears, no fees, and no extra payments. Monthly interest and regular payments
round to cents; the last payment clears the remaining balance. A very small loan
may have a zero rounded regular payment and a nonzero final payment. Principal
must be at least $0.01, APR is 0–100%, and term is 1–100 whole years.

Depreciation uses full years (1–100). Salvage must be between zero and cost. Methods
are `straight_line` and `double_declining`; the latter uses a remaining-life
straight-line switch when larger, with the last year reconciled to salvage.
Schedules do not implement tax depreciation conventions, MACRS, Section 179,
or bonus depreciation.

`percent_change` uses `(new - old) / old * 100`, retaining the signed denominator
for negative starting values. A zero starting value gives an undefined percentage.
Margin and markup likewise return undefined for a zero denominator.

`calculate` uses bounded floating-point math, not decimal monetary arithmetic.
It supports `+`, `-`, `*`, `/`, `**`, `%`, parentheses, `pi`, `e`, and `round`, `abs`,
`max`, `min`, `sum`, `sqrt`, `log`, `floor`, `ceil`, and two-argument `pow`.
Numeric lists/tuples work with aggregates, e.g. `sum([1, 2, 3])`. No attributes,
indexing, comprehensions, strings, or arbitrary Python calls are executed.
Limits: 4,096 characters, 256 syntax-tree nodes, 32 nesting levels, and finite
real intermediates/results. Currency formatting allows 0–20 decimal places.

## CLI examples

Every command accepts `--json` for the same structured result returned by MCP.

```bash
finance-calc-mcp calc '185000 * 0.21'
finance-calc-mcp margin 850000 612000
finance-calc-mcp tax 185000 single --tax-year 2026 --json
finance-calc-mcp tax 185000 single --tax-year 2024
finance-calc-mcp se-tax 95000 --tax-year 2026 --filing-status single
finance-calc-mcp se-tax 100000 --tax-year 2026 --filing-status married_jointly \
  --social-security-wages 150000 --medicare-wages 250000 \
  --spouse-net-self-employment-income 50000
finance-calc-mcp payroll 95000 3.4 --tax-year 2026 \
  --state-suta-wage-base 15000 --futa-credit-pct 5.1
finance-calc-mcp amortize 400000 6.5 30 --schedule
finance-calc-mcp depreciation 50000 5 5000 --method double_declining
finance-calc-mcp break-even 120000 49.99 18.50
finance-calc-mcp pct-change 1200000 1485000
finance-calc-mcp format 1234567.89 --decimals 2
```

## Structured results

Every successful result contains `tool`, `tax_year` (null for nontax tools),
`inputs`, `results`, `assumptions`, `sources`, and `data_reviewed_on` (null when
there is no tax data). Schedules and brackets are arrays in `results`.

For example, `finance-calc-mcp margin 850000 612000 --json` returns these result
fields (within the full envelope):

```json
{
  "gross_profit": "238000.00",
  "gross_margin_pct": "28.0000",
  "markup_pct": "38.8889"
}
```

MCP errors set `isError=true`. CLI errors write a concise message to stderr and
exit nonzero. Text layout is intended for people; integrations should consume
structured content or `--json`.

## Development and release

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
uv export --locked --no-dev --no-emit-project -o /tmp/finance-calc-requirements.txt
uvx pip-audit -r /tmp/finance-calc-requirements.txt --no-deps --disable-pip
uv build
```

CI tests and audits dependencies on Python 3.10 and 3.14 on pushes, pull requests,
and weekly. Tests cover independent IRS bracket anchors, tax thresholds, schedule
reconciliation, input rejection, CLI use, and modern/legacy stdio connections.
Dependabot checks uv and GitHub Actions weekly. Keep security floors in
`pyproject.toml` and the tested dependency versions in `uv.lock` up to date.

The `Publish to PyPI` workflow builds, tests, and audits a version tag, then uses
trusted publishing with the GitHub environment `pypi`. Configure the PyPI trusted
publisher for owner `FellowTraveler`, repository `finance-calc-mcp`, workflow
`publish.yml`, and environment `pypi`. After CI passes, push a tag matching the
package version and run:

```bash
gh workflow run publish.yml -f tag=v0.3.0
```

Verify PyPI availability and test a fresh installation before publishing the
GitHub release announcement.

## License

MIT
