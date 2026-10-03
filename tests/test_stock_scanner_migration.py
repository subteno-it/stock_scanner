# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


from odoo.tests import common, tagged

from odoo.addons.stock_scanner.migration import migrate_scenario_code, rewrite_code


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerMigration(common.TransactionCase):
    """The scenarios written for the removed tmp_values helpers are rewritten."""

    def test_rewrite_get_tmp_value(self):
        """get_tmp_value calls must be rewritten to tmp_values.get, keeping the default argument."""
        self.assertEqual(rewrite_code('terminal.get_tmp_value("login")'), 'terminal.tmp_values.get("login")')
        self.assertEqual(
            rewrite_code('terminal.get_tmp_value("x", default=False)'),
            'terminal.tmp_values.get("x", False)',
        )

    def test_rewrite_is_idempotent(self):
        """Already migrated code must be left untouched."""
        code = 'terminal.tmp_values.get("login")'
        self.assertEqual(rewrite_code(code), code)

    def test_legacy_login_scenario_is_migrated(self):
        """Legacy login scenario code must be migrated once and then left untouched."""
        step = self.env.ref("stock_scanner.scanner_scenario_login_step_pwd")
        step.python_code = step.python_code.replace(
            'tmp_values = dict(terminal.tmp_values)\ntmp_values["login"] = message\nterminal.tmp_values = tmp_values',
            'terminal.update_tmp_values({"login": message})',
        )
        transition = self.env.ref("stock_scanner.scanner_scenario_transition_pwd_to_done")
        transition.condition = transition.condition.replace("terminal.tmp_values.get(", "terminal.get_tmp_value(")
        self.assertIn("update_tmp_values", step.python_code)
        self.assertEqual(migrate_scenario_code(self.env), 2)
        self.assertNotIn("update_tmp_values", step.python_code)
        self.assertNotIn("get_tmp_value", transition.condition)
        self.assertEqual(migrate_scenario_code(self.env), 0)
