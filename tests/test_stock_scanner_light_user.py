# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests import tagged

from .common import StockScannerCommon


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerLightUser(StockScannerCommon):
    """The technical user of the terminals can be a light user, the operators log in with their own account."""

    @classmethod
    def setUpClass(cls):
        """Create a light technical user, an operator with stock rights and a terminal."""
        res = super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.sentinel = Users.create({
            "name": "Sentinel light",
            "login": "sentinel_light",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("stock_scanner.group_stock_scanner_sentinel").id,
            ])],
        })
        cls.operator_password = "Operator-pass-2026-xyz"
        cls.operator = Users.create({
            "name": "Operator",
            "login": "scanner_operator",
            "password": cls.operator_password,
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("stock.group_stock_user").id,
            ])],
        })
        cls.terminal = cls.env["scanner.hardware"].create({
            "name": "Light terminal",
            "code": "light1",
            "warehouse_id": cls.env["stock.warehouse"].search([], limit=1).id,
        })
        return res

    def test_sentinel_group_makes_a_light_user(self):
        """A user of the sentinel group, with no other rights, is a light user."""
        self.assertEqual(self.sentinel.role, "light_user")

    def test_stock_user_is_light_too(self):
        """An operator with the Inventory / User right only is a light user as well."""
        self.assertEqual(self.operator.role, "light_user")

    def test_stock_manager_makes_a_regular_user(self):
        """A technical user given the stock manager right is a regular user: no saving then."""
        self.sentinel.group_ids += self.env.ref("stock.group_stock_manager")
        self.assertEqual(self.sentinel.role, "regular_user")

    def test_light_user_logs_the_operator_in(self):
        """The light user logs an operator in, and the terminal then plays with the rights of the operator."""
        Hardware = self.env["scanner.hardware"]
        _act, lines, _value = Hardware.with_user(self.sentinel).scanner_call(self.terminal.code, "menu")
        self.assertEqual(lines, [])

        self.terminal.with_user(self.sentinel).login(self.operator.login, self.operator_password)
        self.assertEqual(self.terminal.user_id, self.operator)

        # The tutorial is reserved for the stock users: only the operator sees it
        _act, lines, _value = Hardware.with_user(self.sentinel).scanner_call(self.terminal.code, "menu")
        self.assertIn("Tutorial", lines)
