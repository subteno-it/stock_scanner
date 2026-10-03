# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# © 2011 Sylvain Garancher <sylvain.garancher@syleam.fr>

import logging

from odoo import api, exceptions, fields, models

logger = logging.getLogger("stock_scanner")


class ScannerScenario(models.Model):
    """Scenario, menu or shortcut displayed on the scanner and executed as a graph of steps."""

    _name = "scanner.scenario"
    _description = "Scenario for scanner"
    _order = "sequence"
    _parent_name = "parent_id"

    @api.model
    def _type_get(self):
        """Return the selectable scenario types.

        Returns:
            list: Selection tuples (value, label).
        """
        return [
            ("scenario", "Scenario"),
            ("menu", "Menu"),
            ("shortcut", "Shortcut"),
        ]

    # ===========================================================================
    # COLUMNS
    # ===========================================================================
    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
        help="Appear on barcode reader screen.",
    )
    sequence = fields.Integer(
        string="Sequence",
        help="Sequence order.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If checked, this scenario is available.",
    )
    model_id = fields.Many2one(
        string="Model",
        comodel_name="ir.model",
        help="Model used for this scenario.",
    )
    step_ids = fields.One2many(
        string="Scenario",
        comodel_name="scanner.scenario.step",
        inverse_name="scenario_id",
        help="Step of the current running scenario.",
    )
    warehouse_ids = fields.Many2many(
        string="Warehouses",
        comodel_name="stock.warehouse",
        relation="scanner_scenario_warehouse_rel",
        column1="scenario_id",
        column2="warehouse_id",
        help="Warehouses for this scenario.",
    )
    notes = fields.Text(
        string="Notes",
        default="Notes\n\n\n",
        help="Store different notes, date and title for modification, etc...",
    )
    parent_id = fields.Many2one(
        string="Parent",
        comodel_name="scanner.scenario",
        ondelete="restrict",
        required=False,
        help="Parent scenario, used to create menus.",
    )
    child_ids = fields.One2many(
        string="Subordinates",
        comodel_name="scanner.scenario",
        inverse_name="parent_id",
        help="",
    )
    type = fields.Selection(
        string="Type",
        selection="_type_get",
        default="scenario",
        required=True,
        help="Defines if this scenario is a menu or an executable scenario.",
    )
    company_id = fields.Many2one(
        string="Company",
        comodel_name="res.company",
        default=lambda self: self.env.user.company_id.id,
        ondelete="restrict",
        required=True,
        help="Company to be used on this scenario.",
    )
    group_ids = fields.Many2many(
        string="Allowed Groups",
        comodel_name="res.groups",
        default=lambda self: [self.env.ref("stock.group_stock_user").id],
        relation="scanner_scenario_res_groups_rel",
        column1="scenario_id",
        column2="group_id",
        help="",
    )
    user_ids = fields.Many2many(
        string="Allowed Users",
        comodel_name="res.users",
        relation="scanner_scenario_res_users_rel",
        column1="scenario_id",
        column2="user_id",
        help="",
    )

    @api.constrains("parent_id")
    def _check_recursion(self):
        """Forbid cycles in the parent/child menu hierarchy.

        Raises:
            ValidationError: If a scenario is its own ancestor.
        """
        if self._has_cycle():
            raise exceptions.ValidationError(
                self.env._("Error ! You can not create recursive scenarios."),
            )

    def copy(self, default=None):
        """Duplicate the scenario with its steps and rewire transitions on the copied steps.

        Steps are copied explicitly because transitions reference steps, so each transition
        must be re-created pointing to the new step ids.

        Args:
            default: Values overriding the copied ones; the name is always prefixed with "Copy of".

        Returns:
            recordset: The new scenario.
        """
        default = default or {}
        default["name"] = self.env._("Copy of %s") % self.name

        scenario_new = super().copy(default)
        step_news = {}
        for step in self.step_ids:
            step_news[step.id] = step.copy({"scenario_id": scenario_new.id}).id
        for trans in self.env["scanner.scenario.transition"].search([("scenario_id", "=", self.id)]):
            trans.copy({
                "from_id": step_news[trans.from_id.id],
                "to_id": step_news[trans.to_id.id],
            })
        return scenario_new

    def action_export_scenario(self):
        """Open the export wizard for this scenario.

        Returns:
            dict: Window action of the export wizard.
        """
        self.ensure_one()
        return self.env.ref("stock_scanner.action_wizard_export_scenario").read()[0]
