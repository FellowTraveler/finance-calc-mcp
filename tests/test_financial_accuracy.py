"""Independent tax-table anchors and reconciliation checks (no production-table oracle)."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D, ROUND_HALF_UP

from finance_calc_mcp.calculations import calculate_result

# Published cumulative tax at each finite bracket ceiling, transcribed from
# IRS Rev. Proc. 2023-34, 2024-40, and 2025-32. Test data intentionally independent.
ANCHORS = {
    (2024, 'single'): [(11600, '1160'), (47150, '5426'), (100525, '17168.50'), (191950, '39110.50'), (243725, '55678.50'), (609350, '183647.25')],
    (2024, 'married_jointly'): [(23200, '2320'), (94300, '10852'), (201050, '34337'), (383900, '78221'), (487450, '111357'), (731200, '196669.50')],
    (2024, 'married_separately'): [(11600, '1160'), (47150, '5426'), (100525, '17168.50'), (191950, '39110.50'), (243725, '55678.50'), (365600, '98334.75')],
    (2024, 'head_of_household'): [(16550, '1655'), (63100, '7241'), (100500, '15469'), (191950, '37417'), (243700, '53977'), (609350, '181954.50')],
    (2025, 'single'): [(11925, '1192.50'), (48475, '5578.50'), (103350, '17651'), (197300, '40199'), (250525, '57231'), (626350, '188769.75')],
    (2025, 'married_jointly'): [(23850, '2385'), (96950, '11157'), (206700, '35302'), (394600, '80398'), (501050, '114462'), (751600, '202154.50')],
    (2025, 'married_separately'): [(11925, '1192.50'), (48475, '5578.50'), (103350, '17651'), (197300, '40199'), (250525, '57231'), (375800, '101077.25')],
    (2025, 'head_of_household'): [(17000, '1700'), (64850, '7442'), (103350, '15912'), (197300, '38460'), (250500, '55484'), (626350, '187031.50')],
    (2026, 'single'): [(12400, '1240'), (50400, '5800'), (105700, '17966'), (201775, '41024'), (256225, '58448'), (640600, '192979.25')],
    (2026, 'married_jointly'): [(24800, '2480'), (100800, '11600'), (211400, '35932'), (403550, '82048'), (512450, '116896'), (768700, '206583.50')],
    (2026, 'married_separately'): [(12400, '1240'), (50400, '5800'), (105700, '17966'), (201775, '41024'), (256225, '58448'), (384350, '103291.75')],
    (2026, 'head_of_household'): [(17700, '1770'), (67450, '7740'), (105700, '16155'), (201750, '39207'), (256200, '56631'), (640600, '191171')],
}


def results(tool, **args):
    return calculate_result(tool, args)['results']


def se(**args):
    return results('self_employment_tax', **{
        'net_self_employment_income': 95000, 'tax_year': 2026, 'filing_status': 'single', **args,
    })


class IncomeTaxTests(unittest.TestCase):
    def test_all_bracket_boundaries(self):
        rates = list(map(D, ['.10', '.12', '.22', '.24', '.32', '.35', '.37']))
        for (year, status), anchors in ANCHORS.items():
            for index, (income, expected) in enumerate(anchors):
                for delta in (-1, -0.01, 0, 0.01, 1):
                    with self.subTest(year=year, status=status, income=income, delta=delta):
                        marginal = rates[index if delta < 0 else index + 1]
                        target = (D(expected) + D(str(delta)) * marginal).quantize(D('.01'), rounding=ROUND_HALF_UP)
                        r = results('us_income_tax_estimate', taxable_income=income + delta,
                                    filing_status=status, tax_year=year)
                        self.assertEqual(D(r['federal_income_tax']), target)
                        self.assertEqual(sum(D(b['tax']) for b in r['brackets']), target)

    def test_tax_year_changes_result_and_preserves_history(self):
        for year, expected in [(2024, '37442.50'), (2025, '37247.00'), (2026, '36998.00')]:
            payload = calculate_result('us_income_tax_estimate', {
                'taxable_income': 185000, 'filing_status': 'single', 'tax_year': year,
            })
            self.assertEqual(payload['results']['federal_income_tax'], expected)
            self.assertEqual(payload['tax_year'], year)
            self.assertTrue(payload['sources'])
            self.assertEqual(payload['data_reviewed_on'], '2026-11-20')

    def test_zero_income(self):
        r = results('us_income_tax_estimate', taxable_income=0, filing_status='single', tax_year=2026)
        self.assertEqual(D(r['federal_income_tax']), 0)
        self.assertIsNone(r['effective_rate_pct'])
        self.assertEqual(r['brackets'], [])


class SelfEmploymentTests(unittest.TestCase):
    def test_normal_income(self):
        r = se()
        self.assertEqual(r['net_earnings'], '87732.50')
        self.assertEqual(r['social_security_tax'], '10878.83')
        self.assertEqual(r['medicare_tax'], '2544.24')
        self.assertEqual(r['regular_self_employment_tax'], '13423.07')
        self.assertEqual(r['deductible_half'], '6711.54')

    def test_losses_and_minimum_earnings(self):
        for net in (-10000, 0, 400, 433.12):
            with self.subTest(net=net):
                r = se(net_self_employment_income=net)
                self.assertEqual(D(r['regular_self_employment_tax']), 0)
                self.assertEqual(D(r['deductible_half']), 0)
        r = se(net_self_employment_income=433.13)
        self.assertEqual(r['taxable_se_earnings'], '400.00')
        self.assertEqual(r['regular_self_employment_tax'], '61.20')
        self.assertEqual(r['deductible_half'], '30.60')

    def test_social_security_caps_and_existing_wages(self):
        for year, cap, max_tax in [(2024, 168600, '20906.40'), (2025, 176100, '21836.40'), (2026, 184500, '22878.00')]:
            with self.subTest(year=year):
                r = se(tax_year=year, net_self_employment_income=1000000)
                self.assertEqual(r['social_security_tax'], max_tax)
                for wages, expected in [(cap - 100, '12.40'), (cap, '0.00'), (cap + 100, '0.00')]:
                    r = se(tax_year=year, social_security_wages=wages)
                    self.assertEqual(r['social_security_tax'], expected)
                    self.assertEqual(r['medicare_tax'], '2544.24')

    def test_additional_medicare_statuses_and_deduction(self):
        # $300k profit -> $277,050 earnings. Regular Medicare = $8,034.45.
        for status, threshold, additional in [
            ('single', 200000, '693.45'), ('head_of_household', 200000, '693.45'),
            ('married_jointly', 250000, '243.45'), ('married_separately', 125000, '1368.45'),
        ]:
            with self.subTest(status=status):
                r = se(net_self_employment_income=300000, filing_status=status)
                self.assertEqual(r['additional_medicare_tax_on_combined_se'], additional)
                self.assertEqual(r['deductible_half'], '15456.23')
                self.assertEqual(r['regular_self_employment_tax'], '30912.45')
                # No SE: check every wage threshold immediately below/at/above.
                for delta, expected in [(-1, '0.00'), (0, '0.00'), (1, '0.01')]:
                    r = se(net_self_employment_income=0, filing_status=status, medicare_wages=threshold + delta)
                    self.assertEqual(r['additional_medicare_tax_on_wages'], expected)

    def test_wages_use_threshold_before_se(self):
        r = se(net_self_employment_income=100000, medicare_wages=190000, social_security_wages=184500)
        self.assertEqual(r['additional_medicare_tax_on_wages'], '0.00')
        self.assertEqual(r['additional_medicare_tax_on_combined_se'], '741.15')
        r = se(net_self_employment_income=100000, medicare_wages=210000)
        self.assertEqual(r['additional_medicare_tax_on_wages'], '90.00')
        self.assertEqual(r['additional_medicare_tax_on_combined_se'], '831.15')
        self.assertEqual(r['total_additional_medicare_tax'], '921.15')

    def test_additional_medicare_se_threshold_boundaries(self):
        # These net profits yield rounded earnings just below/at/above the
        # statutory $200k, $250k, and $125k thresholds respectively.
        for status, profits in [
            ('single', (216566.33, 216567.41, 216568.49)),
            ('head_of_household', (216566.33, 216567.41, 216568.49)),
            ('married_jointly', (270708.18, 270709.26, 270710.34)),
            ('married_separately', (135353.55, 135354.63, 135355.71)),
        ]:
            for profit, expected in zip(profits, ('0.00', '0.00', '0.01')):
                with self.subTest(status=status, profit=profit):
                    r = se(net_self_employment_income=profit, filing_status=status)
                    self.assertEqual(r['additional_medicare_tax_on_combined_se'], expected)

    def test_joint_spouse_income_and_losses(self):
        r = se(net_self_employment_income=100000, filing_status='married_jointly',
               medicare_wages=100000, spouse_net_self_employment_income=100000)
        self.assertEqual(r['additional_medicare_tax_on_combined_se'], '312.30')
        self.assertEqual(r['regular_self_employment_tax'], '14129.55')
        r = se(net_self_employment_income=-100000, filing_status='married_jointly',
               medicare_wages=250000, spouse_net_self_employment_income=100000)
        self.assertEqual(r['additional_medicare_tax_on_combined_se'], '831.15')
        self.assertEqual(D(r['regular_self_employment_tax']), 0)
        with self.assertRaises(ValueError):
            se(spouse_net_self_employment_income=1000)


class PayrollTests(unittest.TestCase):
    def test_annual_example_and_state_inputs(self):
        r = results('payroll_summary', gross_annual_salary=95000, tax_year=2026,
                    state_suta_rate=3.4, state_suta_wage_base=15000)
        self.assertEqual(r['employee_social_security'], '5890.00')
        self.assertEqual(r['employee_medicare'], '1377.50')
        self.assertEqual(r['employer_futa'], '42.00')
        self.assertEqual(r['employer_suta'], '510.00')
        self.assertEqual(r['total_employer_cost'], '102819.50')
        self.assertEqual(r['pay_after_fica_before_income_tax_and_other_deductions'], '87732.50')

    def test_wage_caps_withholding_and_no_additional_match(self):
        for year, cap, max_tax in [(2024, 168600, '10453.20'), (2025, 176100, '10918.20'), (2026, 184500, '11439.00')]:
            for salary in (cap - 1, cap, cap + 1):
                r = results('payroll_summary', gross_annual_salary=salary, tax_year=year)
                expected = D(max_tax) - (D('.06') if salary < cap else 0)
                self.assertEqual(D(r['employee_social_security']), expected)
                self.assertEqual(r['employee_social_security'], r['employer_social_security'])
        for salary, withheld in [(199999, '0.00'), (200000, '0.00'), (200001, '0.01'), (300000, '900.00')]:
            r = results('payroll_summary', gross_annual_salary=salary, tax_year=2026)
            self.assertEqual(r['additional_medicare_withheld'], withheld)
            expected_cost = D(salary) + D('11439') + (D(salary) * D('.0145')).quantize(D('.01'), rounding=ROUND_HALF_UP) + 42 + 189
            self.assertEqual(D(r['total_employer_cost']), expected_cost)

    def test_futa_credit_and_unemployment_caps(self):
        for credit, expected in [(5.4, '42.00'), (5.1, '63.00'), (0, '420.00')]:
            r = results('payroll_summary', gross_annual_salary=95000, tax_year=2026, futa_credit_pct=credit)
            self.assertEqual(r['employer_futa'], expected)
        for salary in (6999, 7000, 7001):
            r = results('payroll_summary', gross_annual_salary=salary, tax_year=2026)
            self.assertEqual(r['employer_futa'], '41.99' if salary < 7000 else '42.00')
            self.assertEqual(r['employer_suta'], '188.97' if salary < 7000 else '189.00')


class ScheduleTests(unittest.TestCase):
    def test_depreciation_known_schedules(self):
        r = results('depreciation', asset_cost=10000, useful_life=5, method='double_declining')
        self.assertEqual([row['depreciation'] for row in r['schedule']], ['4000.00', '2400.00', '1440.00', '1080.00', '1080.00'])
        r = results('depreciation', asset_cost=100, useful_life=3)
        self.assertEqual([row['depreciation'] for row in r['schedule']], ['33.33', '33.33', '33.34'])

    def test_depreciation_reconciles(self):
        for cost, salvage in [(0, 0), (100, 100), (50000, 5000), (0.01, 0), (999999999999.99, 123.45)]:
            for life in (1, 3, 5, 100):
                for method in ('straight_line', 'double_declining'):
                    with self.subTest(cost=cost, salvage=salvage, life=life, method=method):
                        r = results('depreciation', asset_cost=cost, salvage_value=salvage, useful_life=life, method=method)
                        total = sum(D(row['depreciation']) for row in r['schedule'])
                        self.assertEqual(total, D(str(cost)) - D(str(salvage)))
                        self.assertEqual(total, D(r['total_depreciated']))
                        self.assertEqual(D(r['ending_book_value']), D(str(salvage)))
                        book = D(str(cost))
                        for row in r['schedule']:
                            self.assertGreaterEqual(D(row['depreciation']), 0)
                            book -= D(row['depreciation'])
                            self.assertEqual(book, D(row['book_value']))
                            self.assertGreaterEqual(book, D(str(salvage)))

    def test_zero_rate_loan(self):
        r = results('loan_amortization', principal=100, annual_rate_pct=0, term_years=1, show_schedule=True)
        self.assertEqual(r['monthly_payment'], '8.33')
        self.assertEqual(r['final_payment'], '8.37')
        self.assertEqual(r['total_paid'], '100.00')
        self.assertEqual(r['total_interest'], '0.00')

    def test_loan_schedule_reconciles_and_matches_summary(self):
        for principal, rate, years in [(400000, 6.5, 30), (12000, 12, 1), (0.01, 0, 100), (1, 100, 100), (1e12, 100, 100), (100, 1e-100, 1)]:
            with self.subTest(principal=principal, rate=rate, years=years):
                args = dict(principal=principal, annual_rate_pct=rate, term_years=years)
                r = results('loan_amortization', **args, show_schedule=True)
                rows = r.pop('schedule')
                self.assertEqual(r, results('loan_amortization', **args))
                self.assertEqual(sum(D(row['principal']) for row in rows), D(str(principal)))
                self.assertEqual(sum(D(row['interest']) for row in rows), D(r['total_interest']))
                self.assertEqual(sum(D(row['payment']) for row in rows), D(r['total_paid']))
                self.assertEqual(D(r['total_paid']) - D(r['total_interest']), D(str(principal)))
                self.assertEqual(D(rows[-1]['balance']), 0)
                balance = D(str(principal))
                for row in rows:
                    self.assertEqual(D(row['payment']), D(row['principal']) + D(row['interest']))
                    self.assertGreaterEqual(D(row['balance']), 0)
                    balance -= D(row['principal'])
                    self.assertEqual(balance, D(row['balance']))
        r = results('loan_amortization', principal=400000, annual_rate_pct=6.5, term_years=30)
        self.assertEqual(r['monthly_payment'], '2528.27')


class ValidationAndGeneralTests(unittest.TestCase):
    def test_undefined_ratios_and_direction(self):
        r = results('gross_margin', revenue=0, cogs=0)
        self.assertIsNone(r['gross_margin_pct'])
        self.assertIsNone(r['markup_pct'])
        for new in (0, 100):
            self.assertIsNone(results('percent_change', old_value=0, new_value=new)['percent_change'])
        self.assertEqual(results('percent_change', old_value=10, new_value=10)['direction'], 'unchanged')
        self.assertEqual(results('percent_change', old_value=-100, new_value=-50)['percent_change'], '-50.0000')

    def test_rounding_and_break_even(self):
        self.assertEqual(results('currency_format', amount=1.005)['formatted'], '$1.01')
        self.assertEqual(results('currency_format', amount=-1.005)['formatted'], '$-1.01')
        r = results('break_even', fixed_costs=100, price_per_unit=10, variable_cost_per_unit=7)
        self.assertEqual(r['whole_units_required'], 34)
        self.assertEqual(r['break_even_units'], '33.3333')
        self.assertEqual(r['revenue_at_whole_units'], '340.00')

    def test_year_and_filing_status_are_required_and_validated(self):
        for year in (None, 2023, 2027, True, '2026'):
            with self.subTest(year=year), self.assertRaises(ValueError):
                results('us_income_tax_estimate', taxable_income=100, filing_status='single', tax_year=year)
        for tool, args in [
            ('us_income_tax_estimate', {'taxable_income': 100, 'filing_status': 'single'}),
            ('self_employment_tax', {'net_self_employment_income': 100, 'filing_status': 'single'}),
            ('payroll_summary', {'gross_annual_salary': 100}),
        ]:
            with self.subTest(tool=tool), self.assertRaises(ValueError):
                calculate_result(tool, args)
        with self.assertRaises(ValueError):
            se(filing_status='unknown')

    def test_invalid_numeric_inputs(self):
        from test_security import EXAMPLES
        from finance_calc_mcp.schemas import INPUT_SCHEMAS
        for tool, args in EXAMPLES.items():
            for key, schema in INPUT_SCHEMAS[tool]['properties'].items():
                if schema['type'] not in ('integer', 'number'):
                    continue
                for bad in (float('nan'), float('inf'), float('-inf'), True, '10', 1e100):
                    with self.subTest(tool=tool, field=key, value=bad), self.assertRaises(ValueError):
                        calculate_result(tool, {**args, key: bad})
        for tool, args in [
            ('depreciation', dict(asset_cost=100, salvage_value=101, useful_life=5)),
            ('depreciation', dict(asset_cost=100, useful_life=5, method='MACRS')),
            ('loan_amortization', dict(principal=0, annual_rate_pct=1, term_years=1)),
            ('loan_amortization', dict(principal=100, annual_rate_pct=-1, term_years=1)),
            ('payroll_summary', dict(gross_annual_salary=100, tax_year=2026, futa_credit_pct=6)),
            ('payroll_summary', dict(gross_annual_salary=100, tax_year=2026, state_suta_wage_base=-1)),
            ('payroll_summary', dict(gross_annual_salary=100, tax_year=2026, state_suta_rate=101)),
            ('us_income_tax_estimate', dict(taxable_income=-1, tax_year=2026, filing_status='single')),
        ]:
            with self.subTest(tool=tool, args=args), self.assertRaises(ValueError):
                calculate_result(tool, args)

    def test_cli_requires_year_and_returns_json(self):
        base = [sys.executable, '-m', 'finance_calc_mcp.server']
        for args in [['tax', '185000', 'single'], ['se-tax', '95000'], ['payroll', '95000']]:
            process = subprocess.run(base + args, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn('--tax-year', process.stderr)
        process = subprocess.run(base + ['tax', '185000', 'single', '--tax-year', '2026', '--json'],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['results']['federal_income_tax'], '36998.00')
        process = subprocess.run(base + ['amortize', '0', '5', '30'], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(process.returncode, 0)
        self.assertNotIn('Traceback', process.stderr)

    def test_cli_tax_options_are_forwarded(self):
        base = [sys.executable, '-m', 'finance_calc_mcp.server']
        cases = [
            (['se-tax', '100000', '--tax-year', '2026', '--filing-status', 'married_jointly',
              '--social-security-wages', '184500', '--medicare-wages', '100000',
              '--spouse-net-self-employment-income', '100000'],
             'additional_medicare_tax_on_combined_se', '312.30'),
            (['payroll', '95000', '3.4', '--tax-year', '2026',
              '--state-suta-wage-base', '15000', '--futa-credit-pct', '5.1'],
             'total_employer_cost', '102840.50'),
        ]
        for args, field, expected in cases:
            with self.subTest(args=args):
                process = subprocess.run(base + args + ['--json'], capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(json.loads(process.stdout)['results'][field], expected)
