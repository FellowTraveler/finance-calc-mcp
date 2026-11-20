"""Pure calculations with explicit assumptions and cent-rounded monetary output."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP, localcontext

from .expressions import safe_eval
from . import tax_data as tax

D = Decimal
ZERO = D('0')
CENT = D('0.01')
MAX_AMOUNT = D('1000000000000')
ROUNDING = 'USD inputs and monetary line items round to cents, half up; totals sum rounded line items.'


def number(value, name, minimum=None, maximum=MAX_AMOUNT):
    if type(value) not in (int, float, Decimal):
        raise ValueError(f'{name} must be a finite number')
    value = D(str(value))
    if not value.is_finite() or abs(value) > maximum or (minimum is not None and value < minimum):
        raise ValueError(f'{name} is outside the supported range')
    return value


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def amount(value, name, minimum=ZERO):
    return money(number(value, name, minimum))


def integer(value, name, minimum, maximum):
    value = number(value, name, D(minimum), D(maximum))
    if value != value.to_integral_value():
        raise ValueError(f'{name} must be a whole number')
    return int(value)


def percentage(numerator, denominator):
    if not denominator:
        return None
    return (numerator / denominator * 100).quantize(D('0.0001'), rounding=ROUND_HALF_UP)


def serializable(value):
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, dict):
        return {key: serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    return value


def result(tool, inputs, values, assumptions=(), sources=(), tax_year=None):
    return serializable({
        'tool': tool, 'tax_year': tax_year, 'inputs': inputs, 'results': values,
        'assumptions': list(assumptions), 'sources': list(sources),
        'data_reviewed_on': tax.REVIEWED_ON if tax_year else None,
    })


def calculate(expression):
    value = safe_eval(expression)
    return result('calculate', {'expression': expression}, {'value': value},
                  ['General expressions use finite floating-point arithmetic.'])


def gross_margin(revenue, cogs):
    revenue, cogs = amount(revenue, 'revenue'), amount(cogs, 'cogs')
    profit = revenue - cogs
    return result('gross_margin', {'revenue': revenue, 'cogs': cogs}, {
        'gross_profit': profit, 'gross_margin_pct': percentage(profit, revenue),
        'markup_pct': percentage(profit, cogs),
    }, [ROUNDING, 'A percentage with a zero denominator is undefined (null).'])


def us_income_tax_estimate(taxable_income, filing_status, tax_year):
    year, status = tax.tax_year(tax_year), tax.filing_status(filing_status)
    income = amount(taxable_income, 'taxable_income')
    lower, total = ZERO, money(ZERO)
    detail = []
    for upper, rate in zip((*tax.BRACKETS[year][status], None), tax.RATES):
        if income <= lower:
            break
        taxable = min(income, D(upper)) - lower if upper is not None else income - lower
        bracket_tax = money(taxable * D(rate))
        total += bracket_tax
        detail.append({'lower_bound': money(lower), 'upper_bound': money(D(upper)) if upper else None,
                       'rate_pct': D(rate) * 100, 'taxable_amount': money(taxable), 'tax': bracket_tax})
        if upper is not None:
            lower = D(upper)
    return result('us_income_tax_estimate', {'taxable_income': income, 'filing_status': status}, {
        'federal_income_tax': total, 'effective_rate_pct': percentage(total, income), 'brackets': detail,
    }, [ROUNDING, 'Ordinary taxable income after deductions; no deductions are subtracted by this tool.',
        'Rate-schedule estimate before credits; excludes capital-gain rates, AMT, NIIT, and state taxes.',
        'Uses rate schedules, not the IRS tax-table income bands used for some returns.'],
        [tax.INCOME_TAX_SOURCES[year]], year)


def se_earnings(net):
    # Normal Schedule SE method only. The $400 test follows the 92.35% adjustment.
    earnings = money(max(ZERO, net) * D('0.9235'))
    return earnings, earnings if earnings >= 400 else ZERO


def self_employment_tax(net_self_employment_income, tax_year, filing_status,
                        social_security_wages=0, medicare_wages=0,
                        spouse_net_self_employment_income=0):
    year, status = tax.tax_year(tax_year), tax.filing_status(filing_status)
    net = amount(net_self_employment_income, 'net_self_employment_income', None)
    ss_wages = amount(social_security_wages, 'social_security_wages')
    wages = amount(medicare_wages, 'medicare_wages')
    spouse_net = amount(spouse_net_self_employment_income, 'spouse_net_self_employment_income', None)
    if spouse_net and status != 'married_jointly':
        raise ValueError('spouse_net_self_employment_income is only valid for married_jointly')
    earnings, base = se_earnings(net)
    _, spouse_base = se_earnings(spouse_net)
    cap = D(tax.SOCIAL_SECURITY_CAPS[year])
    remaining_cap = max(ZERO, cap - ss_wages)
    ss = money(min(base, remaining_cap) * D('0.124'))
    medicare = money(base * D('0.029'))
    regular = ss + medicare
    threshold = D(tax.MEDICARE_THRESHOLDS[status])
    additional_wages = money(max(ZERO, wages - threshold) * D('0.009'))
    additional_se = money(max(ZERO, base + spouse_base - max(ZERO, threshold - wages)) * D('0.009'))
    return result('self_employment_tax', {
        'net_self_employment_income': net, 'filing_status': status,
        'social_security_wages': ss_wages, 'medicare_wages': wages,
        'spouse_net_self_employment_income': spouse_net,
    }, {
        'net_earnings': earnings, 'taxable_se_earnings': base,
        'social_security_wage_cap': money(cap), 'remaining_social_security_cap': money(remaining_cap),
        'social_security_tax': ss, 'medicare_tax': medicare,
        'regular_self_employment_tax': regular, 'deductible_half': money(regular / 2),
        'additional_medicare_threshold': money(threshold),
        'additional_medicare_tax_on_wages': additional_wages,
        'additional_medicare_tax_on_combined_se': additional_se,
        'total_additional_medicare_tax': additional_wages + additional_se,
    }, [ROUNDING,
        'Normal Schedule SE method; excludes optional methods, church employees, and special exemptions.',
        'Social Security wages and regular SE tax concern this individual only; spouse regular SE tax is excluded.',
        'Medicare wages must include both spouses for a joint return; spouse SE profit is supplied separately.',
        'Additional Medicare Tax is return-level liability before withholding credits, separate from regular SE tax.',
        'Additional Medicare Tax is excluded from the deductible half; SE losses do not offset spouse earnings.'],
        [tax.SE_SOURCES[year], tax.SSA_SOURCE, tax.MEDICARE_SOURCE], year)


def payroll_summary(gross_annual_salary, tax_year, state_suta_rate=2.7,
                    state_suta_wage_base=7000, futa_credit_pct=5.4):
    year = tax.tax_year(tax_year)
    gross = amount(gross_annual_salary, 'gross_annual_salary')
    suta_rate = number(state_suta_rate, 'state_suta_rate', ZERO, D(100))
    suta_base = amount(state_suta_wage_base, 'state_suta_wage_base')
    credit = number(futa_credit_pct, 'futa_credit_pct', ZERO, D('5.4'))
    cap = D(tax.SOCIAL_SECURITY_CAPS[year])
    ss = money(min(gross, cap) * D('0.062'))
    medicare = money(gross * D('0.0145'))
    withheld = money(max(ZERO, gross - 200000) * D('0.009'))
    futa_rate = D(6) - credit
    futa = money(min(gross, D(7000)) * futa_rate / 100)
    suta = money(min(gross, suta_base) * suta_rate / 100)
    return result('payroll_summary', {
        'gross_annual_salary': gross, 'state_suta_rate': suta_rate,
        'state_suta_wage_base': suta_base, 'futa_credit_pct': credit,
    }, {
        'social_security_wage_cap': money(cap), 'employee_social_security': ss,
        'employee_medicare': medicare, 'additional_medicare_withheld': withheld,
        'pay_after_fica_before_income_tax_and_other_deductions': gross - ss - medicare - withheld,
        'employer_social_security': ss, 'employer_medicare': medicare,
        'effective_futa_rate_pct': futa_rate, 'employer_futa': futa, 'employer_suta': suta,
        'total_employer_cost': gross + ss + medicare + futa + suta,
    }, [ROUNDING, 'One employee, one employer, full calendar year; all supplied wages are taxable for each modeled tax.',
        'Additional Medicare withholding starts at $200,000 regardless of filing status; final liability may differ.',
        'No employer match for Additional Medicare Tax. Income-tax withholding, benefits, and other deductions excluded.',
        'SUTA rate and wage base are user assumptions, not state-specific guidance (defaults: 2.7% and $7,000).',
        'The default 5.4 percentage-point FUTA credit assumes full eligibility; supply the actual allowed credit, including reductions.'],
        [tax.PAYROLL_SOURCES[year], tax.SSA_SOURCE, tax.MEDICARE_SOURCE], year)


def depreciation(asset_cost, useful_life, salvage_value=0, method='straight_line'):
    cost, salvage = amount(asset_cost, 'asset_cost'), amount(salvage_value, 'salvage_value')
    life = integer(useful_life, 'useful_life', 1, 100)
    if salvage > cost:
        raise ValueError('salvage_value cannot exceed asset_cost')
    if method not in ('straight_line', 'double_declining'):
        raise ValueError('method must be straight_line or double_declining')
    book, total, rows = cost, ZERO, []
    for year in range(1, life + 1):
        remaining = book - salvage
        if method == 'straight_line':
            charge = money((cost - salvage) / life)
        else:
            # Switch to remaining-life straight line when it depreciates faster.
            charge = money(max(book * 2 / life, remaining / (life - year + 1)))
        charge = remaining if year == life else min(remaining, charge)
        book -= charge
        total += charge
        rows.append({'year': year, 'depreciation': charge, 'book_value': book})
    return result('depreciation', {'asset_cost': cost, 'useful_life': life,
                                  'salvage_value': salvage, 'method': method},
                  {'total_depreciated': total, 'ending_book_value': book, 'schedule': rows},
                  [ROUNDING, 'Full-year book depreciation; not MACRS, Section 179, or bonus tax depreciation.',
                   'Double declining switches to remaining-life straight line when larger; final year reconciles to salvage.'])


def loan_amortization(principal, annual_rate_pct, term_years, show_schedule=False):
    principal = amount(principal, 'principal')
    if principal <= 0:
        raise ValueError('principal must be at least $0.01')
    rate_pct = number(annual_rate_pct, 'annual_rate_pct', ZERO, D(100))
    years = integer(term_years, 'term_years', 1, 100)
    if type(show_schedule) is not bool:
        raise ValueError('show_schedule must be boolean')
    n = years * 12
    rate = rate_pct / 1200
    if rate:
        # Stable for tiny rates: avoid cancellation in (1+r)**n - 1.
        growth_sum = sum((1 + rate) ** i for i in range(n))
        unrounded_payment = principal * (1 + rate) ** n / growth_sum
    else:
        unrounded_payment = principal / n
    payment = money(unrounded_payment)
    balance, total_paid, total_interest, rows = principal, ZERO, ZERO, []
    for month in range(1, n + 1):
        if balance == 0:
            break
        interest = money(balance * rate)
        paid = balance + interest if month == n else min(payment, balance + interest)
        principal_paid = paid - interest
        balance -= principal_paid
        total_paid += paid
        total_interest += interest
        rows.append({'month': month, 'payment': paid, 'principal': principal_paid,
                     'interest': interest, 'balance': balance})
    values = {'scheduled_months': n, 'actual_payments': len(rows), 'monthly_payment': payment,
              'final_payment': rows[-1]['payment'], 'total_paid': total_paid,
              'total_interest': total_interest, 'ending_balance': balance,
              'interest_per_dollar_pct': percentage(total_interest, principal)}
    if show_schedule:
        values['schedule'] = rows
    return result('loan_amortization', {'principal': principal, 'annual_rate_pct': rate_pct,
                                      'term_years': years, 'show_schedule': show_schedule}, values,
                  [ROUNDING, 'Fixed nominal annual rate divided by 12, monthly end-of-period payments; no fees or extra payments.',
                   'Monthly interest and regular payment round to cents; final payment is adjusted to clear the balance.'])


def percent_change(old_value, new_value):
    old, new = number(old_value, 'old_value'), number(new_value, 'new_value')
    return result('percent_change', {'old_value': old, 'new_value': new}, {
        'change': new - old, 'percent_change': percentage(new - old, old),
        'direction': 'increase' if new > old else 'decrease' if new < old else 'unchanged',
    }, ['Percent change = (new - old) / old * 100; zero baseline is undefined (null).',
        'Negative baselines retain the signed denominator; direction describes the numeric change.'])


def break_even(fixed_costs, price_per_unit, variable_cost_per_unit):
    fixed = amount(fixed_costs, 'fixed_costs')
    price = amount(price_per_unit, 'price_per_unit')
    variable = amount(variable_cost_per_unit, 'variable_cost_per_unit')
    margin = price - variable
    if margin <= 0:
        raise ValueError('price_per_unit must exceed variable_cost_per_unit')
    units = fixed / margin
    whole_units = int(units.to_integral_value(rounding=ROUND_CEILING))
    return result('break_even', {'fixed_costs': fixed, 'price_per_unit': price,
                                'variable_cost_per_unit': variable}, {
        'contribution_margin_per_unit': margin, 'contribution_margin_ratio_pct': percentage(margin, price),
        'break_even_units': units.quantize(D('0.0001'), rounding=ROUND_HALF_UP),
        'break_even_revenue': money(units * price), 'whole_units_required': whole_units,
        'revenue_at_whole_units': money(D(whole_units) * price),
    }, [ROUNDING, 'Constant selling price and variable cost; whole units round up to cover fixed costs.'])


def currency_format(amount, decimals=2):
    value = number(amount, 'amount')
    decimals = integer(decimals, 'decimals', 0, 20)
    rounded = value.quantize(D(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    return result('currency_format', {'amount': value, 'decimals': decimals},
                  {'formatted': f'${rounded:,.{decimals}f}'}, ['USD; decimal rounding half up.'])


FUNCTIONS = {function.__name__: function for function in (
    calculate, gross_margin, us_income_tax_estimate, self_employment_tax,
    payroll_summary, depreciation, loan_amortization, percent_change, break_even, currency_format,
)}


def calculate_result(name, args):
    from .schemas import validate_arguments
    validate_arguments(name, args)
    # Enough precision for the supported money range and 20-place currency format.
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_UP
        return FUNCTIONS[name](**args)


def render_result(payload):
    name, values = payload['tool'], payload['results']
    if name == 'currency_format':
        return values['formatted']
    if name == 'calculate':
        return f"Result: {values['value']:,.2f}\n(raw: {values['value']})"

    def display(value):
        if value is None:
            return 'undefined'
        if isinstance(value, str):
            try:
                return format(D(value), ',f')
            except InvalidOperation:
                pass
        return str(value)

    title = name.replace('_', ' ').title()
    if payload['tax_year']:
        title = f"{payload['tax_year']} {title}"
    lines = [title]
    for key, value in values.items():
        if isinstance(value, list):
            lines.append(key.title() + ':')
            for row in value:
                prefix = ''
                if 'year' in row:
                    prefix = f"Year {row['year']:>2}: "
                elif 'month' in row:
                    prefix = f"Month {row['month']:>4}: "
                lines.append(prefix + '  '.join(f"{k.replace('_', ' ').title()}: {'unbounded' if k == 'upper_bound' and v is None else display(v)}"
                                               for k, v in row.items() if k not in ('year', 'month')))
        else:
            lines.append(f"{key.replace('_', ' ').title()}: {display(value)}")
    lines += ['Assumptions:'] + ['- ' + item for item in payload['assumptions']]
    if payload['sources']:
        lines += [f"Sources (reviewed {payload['data_reviewed_on']}):"] + payload['sources']
    return '\n'.join(lines)
