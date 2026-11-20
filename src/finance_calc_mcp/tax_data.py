"""Reviewed annual tax data. Never infer a tax year from the system clock.

Only ordinary-income rate schedules are included (not IRS tax-table bands,
deductions, credits, capital gains, AMT, or state income tax).
"""

REVIEWED_ON = "2026-11-20"
RATES = ("0.10", "0.12", "0.22", "0.24", "0.32", "0.35", "0.37")
BRACKETS = {
    2024: {
        "single": (11600, 47150, 100525, 191950, 243725, 609350),
        "married_jointly": (23200, 94300, 201050, 383900, 487450, 731200),
        "married_separately": (11600, 47150, 100525, 191950, 243725, 365600),
        "head_of_household": (16550, 63100, 100500, 191950, 243700, 609350),
    },
    2025: {
        "single": (11925, 48475, 103350, 197300, 250525, 626350),
        "married_jointly": (23850, 96950, 206700, 394600, 501050, 751600),
        "married_separately": (11925, 48475, 103350, 197300, 250525, 375800),
        "head_of_household": (17000, 64850, 103350, 197300, 250500, 626350),
    },
    2026: {
        "single": (12400, 50400, 105700, 201775, 256225, 640600),
        "married_jointly": (24800, 100800, 211400, 403550, 512450, 768700),
        "married_separately": (12400, 50400, 105700, 201775, 256225, 384350),
        "head_of_household": (17700, 67450, 105700, 201750, 256200, 640600),
    },
}
SOCIAL_SECURITY_CAPS = {2024: 168600, 2025: 176100, 2026: 184500}
INCOME_TAX_SOURCES = {
    2024: "https://www.irs.gov/pub/irs-drop/rp-23-34.pdf",
    2025: "https://www.irs.gov/pub/irs-drop/rp-24-40.pdf",
    2026: "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
}
SSA_SOURCE = "https://www.ssa.gov/oact/cola/cbb.html"
SE_SOURCES = {
    year: f"https://www.irs.gov/pub/irs-prior/i1040sse--{year}.pdf"
    for year in (2024, 2025)
}
SE_SOURCES[2026] = "https://www.irs.gov/instructions/i1040sse"
PAYROLL_SOURCES = {
    year: f"https://www.irs.gov/pub/irs-prior/p15--{year}.pdf"
    for year in (2024, 2025)
}
PAYROLL_SOURCES[2026] = "https://www.irs.gov/publications/p15"
MEDICARE_SOURCE = "https://www.irs.gov/businesses/small-businesses-self-employed/questions-and-answers-for-the-additional-medicare-tax"
MEDICARE_THRESHOLDS = {
    "single": 200000, "married_jointly": 250000,
    "married_separately": 125000, "head_of_household": 200000,
}


def tax_year(value):
    if type(value) is not int or value not in BRACKETS:
        raise ValueError("tax_year is required and must be one of: 2024, 2025, 2026")
    return value


def filing_status(value):
    if not isinstance(value, str) or value not in MEDICARE_THRESHOLDS:
        raise ValueError("filing_status must be one of: " + ", ".join(MEDICARE_THRESHOLDS))
    return value
