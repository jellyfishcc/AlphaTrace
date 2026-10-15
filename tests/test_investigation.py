import unittest

from tracelab.investigation import prepare_investigation


class InvestigationTests(unittest.TestCase):
    def plan(self, net='-10', cash='20', status='calculated'):
        return prepare_investigation([
            dict(item_id='net_profit', difference=net, status=status),
            dict(item_id='operating_cashflow', difference=cash, status='calculated'),
            dict(item_id='parent_profit', difference='-30', status='calculated')])

    def test_matching_signal_adds_cashflow_investigation(self):
        plan = self.plan()
        self.assertEqual(plan['signals'][0]['profit_basis'], 'net_profit')
        self.assertEqual(len(plan['investigation_tasks']), 2)
        self.assertFalse(plan['agent_executed'])

    def test_missing_or_blocked_does_not_trigger(self):
        for net, status in [('', 'calculated'), ('-10', 'blocked')]:
            plan = self.plan(net=net, status=status)
            self.assertEqual(plan['signals'], [])
            self.assertEqual(len(plan['investigation_tasks']), 1)

    def test_no_signal_still_analyzes_and_does_not_use_parent_as_net(self):
        for net, cash in [('10', '20'), ('-10', '0'), ('-10', '-20')]:
            plan = self.plan(net=net, cash=cash)
            self.assertEqual(plan['signals'], [])
            self.assertEqual(plan['investigation_tasks'][0]['id'], 'layered_profit_analysis')
        self.assertEqual([r['item_id'] for r in self.plan()['profit_chain']],
                         ['operating_profit', 'pretax_profit', 'net_profit', 'minority_profit', 'parent_profit'])
