# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Copyright 2017 SYLEAM Info Services

from odoo.tests import tagged

from .common import StockScannerCommon


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerScenarioExecution(StockScannerCommon):
    """Cover the replies of the scanner hardware to menu, restart, back and end actions."""

    def setUp(self):
        """Load the demo hardware and reset its current scenario."""
        ret = super().setUp()

        self.hardware = self.env.ref("stock_scanner.scanner_hardware_1")
        # Reset the current scenario
        # Just in case the database has been manually used
        self.hardware.empty_scanner_values()

        return ret

    def test_display_empty_submenu(self):
        """Selecting an empty submenu without a running scenario must answer that the scenario is not found."""
        # Call to the scanner are done on the model using the scanner code
        scanner_hardware = self.env["scanner.hardware"]

        # Create an empty submenu
        menu = self.env["scanner.scenario"].create({
            "name": "Menu",
            "type": "menu",
        })

        # Call an action without any scenario running
        ret = scanner_hardware.scanner_call(self.hardware.code, action="action", message=menu.name)
        self.assertEqual(ret, ("R", ["Scenario not found"], 0))

    def test_unknown_action_without_scenario(self):
        """An unknown action without a running scenario must be answered as unknown with the message."""
        # Call to the scanner are done on the model using the scanner code
        scanner_hardware = self.env["scanner.hardware"]

        # Call an action without any scenario running
        message = "Some message"
        ret = scanner_hardware.scanner_call(
            self.hardware.code,
            action="action",
            transition_type="scanner",
            message=message,
        )
        self.assertEqual(ret, ("U", message, 0))

    def test_unknown_action_with_scenario(self):
        """An unknown action inside a running scenario must be rejected with an error."""
        # Call to the scanner are done on the model using the scanner code
        scanner_hardware = self.env["scanner.hardware"]

        # Enter a scenario
        step_types_scenario = self.env.ref("stock_scanner.scanner_scenario_step_types")
        ret = scanner_hardware.scanner_call(self.hardware.code, action="action", message="Step types")
        self.assertEqual(self.hardware.scenario_id, step_types_scenario)

        # Call an action without any scenario running
        ret = scanner_hardware.scanner_call(self.hardware.code, action="unknown")
        self.assertEqual(ret, ("R", ["Unknown action"], 0))

    def test_display_restart_from_main_menu(self):
        """Restarting from the main menu must display the root scenarios list."""
        # Call to the scanner are done on the model using the scanner code
        scanner_hardware = self.env["scanner.hardware"]

        # Call an action without any scenario running
        ret = scanner_hardware.scanner_call(self.hardware.code, action="restart")
        self.assertEqual(ret, ("L", ["Tutorial"], 0))

    def test_display_restart_from_scenario(self):
        """Restarting inside a scenario must return the first step again."""
        # Call to the scanner are done on the model using the scanner code
        scanner_hardware = self.env["scanner.hardware"]

        # Enter a scenario
        step_types_scenario = self.env.ref("stock_scanner.scanner_scenario_step_types")
        ret = scanner_hardware.scanner_call(self.hardware.code, action="action", message="Step types")
        self.assertEqual(self.hardware.scenario_id, step_types_scenario)

        # Call an action without any scenario running
        new_ret = scanner_hardware.scanner_call(self.hardware.code, action="restart")
        self.assertEqual(new_ret, ret)

    def test_display_back_from_main_menu(self):
        """Going back from the main menu must display the root scenarios list."""
        # Call to the scanner are done on the model using the scanner code
        scanner_hardware = self.env["scanner.hardware"]

        # Call an action without any scenario running
        new_ret = scanner_hardware.scanner_call(self.hardware.code, action="back")
        self.assertEqual(new_ret, ("L", ["Tutorial"], 0))

    def test_display_scanner_end(self):
        """Ending a running scenario must return the finished message."""
        # Call to the scanner are done on the model using the scanner code
        scanner_hardware = self.env["scanner.hardware"]

        # Enter a scenario
        step_types_scenario = self.env.ref("stock_scanner.scanner_scenario_step_types")
        ret = scanner_hardware.scanner_call(self.hardware.code, action="action", message="Step types")
        self.assertEqual(self.hardware.scenario_id, step_types_scenario)

        # End the scenario
        ret = scanner_hardware.scanner_end(self.hardware.code)
        self.assertEqual(ret, ("F", ["This scenario", "is finished"], ""))
