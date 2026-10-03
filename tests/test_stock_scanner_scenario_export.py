# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Copyright 2020 Florent de Labarre

from odoo.tests import common, tagged


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerScenarioExport(common.TransactionCase):
    """Cover the export of scenarios through the export wizard."""

    def test_scenario_export(self):
        """Exporting a scenario, as an update or as a copy, must complete without error."""
        scenario_tested = self.env.ref("stock_scanner.scanner_scenario_tutorial")
        wiz = self.env["wizard.export.scenario"].create({"scenario_ids": [(6, 0, [scenario_tested.id])]})
        wiz.action_export()

        wiz = self.env["wizard.export.scenario"].create({
            "scenario_ids": [(6, 0, [scenario_tested.id])],
            "is_copy": True,
        })
        wiz.action_export()
