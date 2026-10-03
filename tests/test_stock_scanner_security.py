# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


from odoo.exceptions import AccessError
from odoo.tests import common, tagged


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerSecurity(common.TransactionCase):
    """Scenarios are only visible to the users and groups they allow."""

    @classmethod
    def setUpClass(cls):
        """Create a restricted scenario, a stock manager, an allowed user and an other user."""
        res = super().setUpClass()
        cls.scenario = cls.env["scanner.scenario"].create({
            "name": "Restricted scenario",
            "type": "scenario",
            "group_ids": [(6, 0, [cls.env.ref("stock.group_stock_user").id])],
        })
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.manager = Users.create({
            "name": "Stock manager",
            "login": "scanner_manager",
            "group_ids": [(6, 0, [cls.env.ref("stock.group_stock_manager").id])],
        })
        cls.allowed_user = Users.create({
            "name": "Allowed user",
            "login": "scanner_allowed",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.other_user = Users.create({
            "name": "Other user",
            "login": "scanner_other",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.scenario.user_ids = cls.allowed_user
        return res

    def _visible_to(self, user):
        """Check the scenario visibility.

        Args:
            user: The ``res.users`` record searching the scenarios.

        Returns:
            True if the restricted scenario is found by this user.
        """
        return self.scenario in self.env["scanner.scenario"].with_user(user).search([])

    def test_implied_group_grants_access(self):
        """A stock manager must see the scenario through the group it implies."""
        self.assertTrue(self._visible_to(self.manager))

    def test_allowed_user_has_access(self):
        """A user explicitly allowed on the scenario must see it."""
        self.assertTrue(self._visible_to(self.allowed_user))

    def test_other_user_has_no_access(self):
        """A user neither allowed nor in an allowed group must not see the scenario."""
        self.assertFalse(self._visible_to(self.other_user))

    def test_export_wizard_is_reserved_to_stock_managers(self):
        """Stock managers can use the export wizard while other users get an AccessError."""
        Wizard = self.env["wizard.export.scenario"]
        values = {"scenario_ids": [(6, 0, self.scenario.ids)]}
        wizard = Wizard.with_user(self.manager).create(values)
        wizard.with_user(self.manager).action_export()
        self.assertTrue(wizard.with_user(self.manager).zip_file)
        with self.assertRaises(AccessError):
            Wizard.with_user(self.other_user).create(values)
