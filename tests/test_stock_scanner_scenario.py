# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Copyright 2017 SYLEAM Info Services

from odoo import exceptions
from odoo.tests import common, tagged


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerScenario(common.TransactionCase):
    """Cover the constraints of scanner scenarios."""

    def test_recursive_scenarios(self):
        """A recursive scenario hierarchy must raise a ValidationError."""
        parent_scenario = self.env.ref("stock_scanner.scanner_scenario_tutorial")
        child_scenario = self.env.ref("stock_scanner.scanner_scenario_sentinel")
        with self.assertRaises(exceptions.ValidationError):
            parent_scenario.parent_id = child_scenario
