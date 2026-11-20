# Tax data provenance and review

Reviewed on **2026-11-20**. Supported tax years: **2024, 2025, 2026**.
The caller must select a year. Unsupported years fail; the server never substitutes
the current year or the nearest table. New-year support requires a reviewed release.

## Authoritative data

| Tax year | Ordinary-income rate schedules | Social Security wage cap |
|---|---|---|
| 2024 | [Rev. Proc. 2023-34, section 3.01](https://www.irs.gov/pub/irs-drop/rp-23-34.pdf) | $168,600 |
| 2025 | [Rev. Proc. 2024-40, section 2.01](https://www.irs.gov/pub/irs-drop/rp-24-40.pdf) | $176,100 |
| 2026 | [Rev. Proc. 2025-32, section 4.01](https://www.irs.gov/pub/irs-drop/rp-25-32.pdf) | $184,500 |

Wage caps: [SSA contribution and benefit base history](https://www.ssa.gov/oact/cola/cbb.html).
The 2025 changes to deductions in Rev. Proc. 2025-32 do not affect this tool's
ordinary rate-schedule input, which is taxable income **after deductions**.
No standard deduction is embedded in the calculator.

Normal-method SE calculations follow [Schedule SE instructions](https://www.irs.gov/instructions/i1040sse),
with [2024](https://www.irs.gov/pub/irs-prior/i1040sse--2024.pdf) and
[2025](https://www.irs.gov/pub/irs-prior/i1040sse--2025.pdf) archived versions.
Additional Medicare rules and the distinction between liability and withholding
follow the [IRS Additional Medicare Tax Q&A](https://www.irs.gov/businesses/small-businesses-self-employed/questions-and-answers-for-the-additional-medicare-tax).
Employer FICA and FUTA follow [Publication 15](https://www.irs.gov/publications/p15),
with [2024](https://www.irs.gov/pub/irs-prior/p15--2024.pdf) and
[2025](https://www.irs.gov/pub/irs-prior/p15--2025.pdf) archived versions.
Live IRS URLs can roll forward; use the year-specific archives when maintaining
historical behavior. Returned source links identify the reviewed guidance.

## Modeling choices

- Ordinary income only; four filing statuses. No deductions, credits, capital-gain
  schedules, AMT, NIIT, or state income tax. No IRS tax-table band lookup.
- Normal-method SE earnings use 92.35% of positive net profit, rounded to cents,
  followed by the $400 test. Optional methods and special categories are excluded.
- Regular SE tax and its deductible half belong to one individual. Joint-return
  Additional Medicare liability includes both spouses' Medicare wages and eligible
  SE earnings. Each spouse's SE earnings are calculated separately; losses are not
  netted across spouses. RRTA compensation is outside this estimator's scope.
- Payroll models full-year taxable wages from one employer. State unemployment
  inputs and the allowable FUTA credit are supplied assumptions, not live state
  rules. Final employee Additional Medicare liability is not inferred from payroll
  withholding.
- Monetary inputs and line items use cents with half-up rounding; totals sum line
  items. This is an estimate convention, not an IRS filing/whole-dollar rounding
  engine. Results disclose these limits alongside the selected year and sources.

## Annual review procedure

Review in October after annual IRS/SSA announcements and again in January before
supporting the new tax year. Also review when relevant legislation or corrected
guidance is issued. Dependency audits do not validate tax law.

1. Read the year's IRS revenue procedure and subsequent corrections/legislation.
   Confirm every bracket for all supported statuses and the SSA wage base.
2. Review Schedule SE, Form 8959/Additional Medicare guidance, and Publication 15
   for changes to rates, thresholds, credit rules, and assumptions. Check archived
   years rather than replacing historical data with current values.
3. Update `tax_data.py`, source links, supported-year CLI choices, documentation,
   and `REVIEWED_ON` only after completing the review. Keep published historical
   tables unless an authoritative correction requires a documented fix.
4. Independently transcribe the IRS cumulative tax amounts into test fixtures.
   Test below/at/above each bracket, wage cap, and surtax threshold. Include wage
   coordination, both-spouse cases, losses, minimum earnings, and deduction rules.
5. Run the full test suite and dependency audit on the supported Python versions.
   Confirm MCP schemas, CLI help, errors, assumptions, and JSON examples agree.
6. Publish a versioned release with changes and source references. Do not scrape
   and apply new tax tables automatically during user calculations.

The `Tax data review` GitHub workflow runs in January and October. It fails when
the current calendar year is unsupported or the recorded review is over a year
old. A green check confirms freshness metadata only; it does not replace the
source review above. It can also be run manually after a data update.
