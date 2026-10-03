# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Copyright 2017 SYLEAM Info Services

from odoo import exceptions
from odoo.tests import common, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerScenarioTransition(common.TransactionCase):
    """Cover the constraints of scanner scenario transitions."""

    def test_transition_scenarios(self):
        """A transition linking steps of different scenarios must raise a ValidationError."""
        transition = self.env.ref("stock_scanner.scanner_scenario_transition_sentinel_intro_scroll")
        other_scenario_step = self.env.ref("stock_scanner.scanner_scenario_step_step_types_introduction")
        with self.assertRaises(exceptions.ValidationError):
            transition.to_id = other_scenario_step

    def test_transition_condition_syntax(self):
        """A transition condition with a syntax error must raise a ValidationError."""
        transition = self.env.ref("stock_scanner.scanner_scenario_transition_sentinel_intro_scroll")
        with self.assertRaises(exceptions.ValidationError), mute_logger("stock_scanner"):
            transition.condition = "function("
