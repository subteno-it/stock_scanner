# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Copyright 2017 SYLEAM Info Services

from odoo import exceptions
from odoo.tests import common, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerScenarioStep(common.TransactionCase):
    """Cover the constraints of scanner scenario steps."""

    def test_step_code_syntax(self):
        """A step python code with a syntax error must raise a ValidationError."""
        step = self.env.ref("stock_scanner.scanner_scenario_step_sentinel_introduction")
        with self.assertRaises(exceptions.ValidationError), mute_logger("stock_scanner"):
            step.python_code = "function("
