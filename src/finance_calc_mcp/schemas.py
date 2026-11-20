"""Shared MCP and CLI input contracts; output values preserve decimal precision."""
import math
from jsonschema import Draft202012Validator
from .tax_data import BRACKETS, MEDICARE_THRESHOLDS

LIMIT = 1_000_000_000_000


def numeric(description, minimum=0, maximum=LIMIT, **extra):
    return {'type': 'number', 'description': description, 'minimum': minimum, 'maximum': maximum, **extra}


YEAR = {'type': 'integer', 'enum': list(BRACKETS), 'description': 'Explicit tax year; no default.'}
STATUS = {'type': 'string', 'enum': list(MEDICARE_THRESHOLDS), 'description': 'Federal filing status.'}
YEARS = {'type': 'integer', 'minimum': 1, 'maximum': 100}
DECIMALS = {'type': 'integer', 'minimum': 0, 'maximum': 20, 'default': 2}

# name: (description, properties, required)
DEFINITIONS = {
    'calculate': ('Evaluate a bounded numeric math expression.', {
        'expression': {'type': 'string', 'maxLength': 4096},
    }, ['expression']),
    'gross_margin': ('Calculate gross profit, margin, and markup; undefined percentages are null.', {
        'revenue': numeric('Total revenue in USD.'), 'cogs': numeric('Cost of goods sold in USD.'),
    }, ['revenue', 'cogs']),
    'us_income_tax_estimate': ('Ordinary federal income-tax rate-schedule estimate from taxable income, before credits. Requires tax year.', {
        'taxable_income': numeric('USD taxable income after deductions; deductions are NOT subtracted by this tool.'),
        'filing_status': STATUS, 'tax_year': YEAR,
    }, ['taxable_income', 'filing_status', 'tax_year']),
    'self_employment_tax': ('Individual regular SE tax and deductible half, plus separate return-level Additional Medicare Tax. Normal method only.', {
        'net_self_employment_income': numeric('This individual\'s combined business profit or loss in USD.', -LIMIT),
        'tax_year': YEAR, 'filing_status': STATUS,
        'social_security_wages': numeric('This individual\'s Social Security wages/tips; excludes spouse wages.', default=0),
        'medicare_wages': numeric('Total Medicare wages; include BOTH spouses if filing jointly.', default=0),
        'spouse_net_self_employment_income': numeric('Spouse business profit/loss; joint returns only. Used for Additional Medicare, not spouse regular SE tax.', -LIMIT, default=0),
    }, ['net_self_employment_income', 'tax_year', 'filing_status']),
    'payroll_summary': ('Annual one-employer payroll estimate: FICA withholding and employer costs, excluding income-tax withholding and benefits.', {
        'gross_annual_salary': numeric('Annual wages taxable for all modeled taxes, USD.'), 'tax_year': YEAR,
        'state_suta_rate': numeric('Assumed state unemployment percentage; no state lookup.', maximum=100, default=2.7),
        'state_suta_wage_base': numeric('Assumed state unemployment wage base, USD; varies by state.', default=7000),
        'futa_credit_pct': numeric('Allowed FUTA credit in percentage points, including credit reductions. 5.4 assumes full eligibility.', maximum=5.4, default=5.4),
    }, ['gross_annual_salary', 'tax_year']),
    'depreciation': ('Full-year book depreciation, straight line or double declining with a straight-line switch; not MACRS.', {
        'asset_cost': numeric('Asset cost in USD.'), 'useful_life': YEARS,
        'salvage_value': numeric('Residual value in USD, no greater than cost.', default=0),
        'method': {'type': 'string', 'enum': ['straight_line', 'double_declining'], 'default': 'straight_line'},
    }, ['asset_cost', 'useful_life']),
    'loan_amortization': ('Fixed-rate monthly loan schedule with cent-rounded payments and an adjusted final payment.', {
        'principal': numeric('Loan principal in USD.', minimum=0.01),
        'annual_rate_pct': numeric('Nominal annual interest rate percentage; no fees.', maximum=100),
        'term_years': YEARS, 'show_schedule': {'type': 'boolean', 'default': False},
    }, ['principal', 'annual_rate_pct', 'term_years']),
    'percent_change': ('Calculate signed percentage change; zero baseline returns null.', {
        'old_value': numeric('Original value.', -LIMIT), 'new_value': numeric('New value.', -LIMIT),
    }, ['old_value', 'new_value']),
    'break_even': ('Calculate fractional break-even units and whole units needed to cover fixed costs.', {
        'fixed_costs': numeric('Fixed costs in USD.'), 'price_per_unit': numeric('Unit selling price in USD.'),
        'variable_cost_per_unit': numeric('Variable unit cost in USD.'),
    }, ['fixed_costs', 'price_per_unit', 'variable_cost_per_unit']),
    'currency_format': ('Format USD using decimal half-up rounding.', {
        'amount': numeric('Amount in USD.', -LIMIT), 'decimals': DECIMALS,
    }, ['amount']),
}
INPUT_SCHEMAS = {
    name: {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}
    for name, (_, properties, required) in DEFINITIONS.items()
}
OUTPUT_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['tool', 'tax_year', 'inputs', 'results', 'assumptions', 'sources', 'data_reviewed_on'],
    'properties': {
        'tool': {'type': 'string', 'enum': list(DEFINITIONS)},
        'tax_year': {'type': ['integer', 'null'], 'enum': [None, *BRACKETS]},
        'inputs': {'type': 'object'},
        'results': {'type': 'object', 'description': 'Monetary values are exact decimal strings in USD; percentages are decimal strings; undefined ratios are null.'},
        'assumptions': {'type': 'array', 'items': {'type': 'string'}},
        'sources': {'type': 'array', 'items': {'type': 'string'}},
        'data_reviewed_on': {'type': ['string', 'null']},
    },
}
VALIDATORS = {name: Draft202012Validator(schema) for name, schema in INPUT_SCHEMAS.items()}


def validate_arguments(name, args):
    if name not in VALIDATORS:
        raise ValueError(f'Unknown tool: {name}')
    if not isinstance(args, dict):
        raise ValueError('Tool arguments must be an object')
    for key, value in args.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f'{key} must be finite')
    error = next(VALIDATORS[name].iter_errors(args), None)
    if error:
        field = '.'.join(map(str, error.path)) or 'arguments'
        # Avoid reflecting arbitrarily large untrusted values in errors.
        raise ValueError(f'Invalid {field}: {error.message[:200]}')
