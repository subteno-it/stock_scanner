# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests import TransactionCase


class StockScannerCommon(TransactionCase):
    """Shared fixture isolating the tests from the data of the database.

    The scanner menus list every scenario the user can see, so tests comparing them would fail on a database that
    holds other scenarios (customer test data, scenarios of other modules).
    """

    @classmethod
    def setUpClass(cls):
        """Archive the scenarios that do not belong to the stock_scanner module, within the test transaction.

        Returns:
            The result of the parent ``setUpClass``.
        """
        res = super().setUpClass()
        module_scenario_ids = (
            cls.env["ir.model.data"]
            .search([("model", "=", "scanner.scenario"), ("module", "=", "stock_scanner")])
            .mapped("res_id")
        )
        cls.env["scanner.scenario"].search([("id", "not in", module_scenario_ids)]).write({"active": False})
        return res
