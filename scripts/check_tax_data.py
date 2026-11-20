"""Scheduled maintenance gate; not a claim that tax rules have not changed."""
from datetime import date

from finance_calc_mcp.tax_data import BRACKETS, REVIEWED_ON

today = date.today()
reviewed = date.fromisoformat(REVIEWED_ON)
problems = []
if today.year not in BRACKETS:
    problems.append(f"Tax year {today.year} is not supported.")
if (today - reviewed).days > 365:
    problems.append(f"Tax data was last reviewed on {reviewed}, over a year ago.")
if reviewed > today:
    problems.append("The recorded review date is in the future.")
print(f"Supported years: {sorted(BRACKETS)}; last source review: {reviewed}")
print("Follow TAX_DATA.md before updating tax data or advancing the review date.")
if problems:
    raise SystemExit("\n".join(problems))
