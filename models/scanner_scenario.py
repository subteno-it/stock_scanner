# © 2011 Sylvain Garancher <sylvain.garancher@syleam.fr>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import _, api, exceptions, fields, models

logger = logging.getLogger("stock_scanner")


class ScannerScenario(models.Model):
    _name = "scanner.scenario"
    _description = "Scenario for scanner"
    _order = "sequence"
    _parent_name = "parent_id"

    @api.model
    def _type_get(self):
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
        help="Sequence order."
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If checked, this scenario is available."
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
        help="Store different notes, date and title for modification, etc...",
        default="Notes\n\n\n",
    )
    parent_id = fields.Many2one(
        string="Parent",
        comodel_name="scanner.scenario",
        required=False,
        ondelete="restrict",
        help="Parent scenario, used to create menus.",
    )
    child_ids = fields.One2many(
        string="Subordinates",
        comodel_name="scanner.scenario",
        inverse_name="parent_id",
    )
    type = fields.Selection(
        string="Type",
        selection="_type_get",
        required=True,
        default="scenario",
        help="Defines if this scenario is a menu or an executable scenario.",
    )
    company_id = fields.Many2one(
        string="Company",
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.user.company_id.id,
        ondelete="restrict",
        help="Company to be used on this scenario.",
    )
    group_ids = fields.Many2many(
        string="Allowed Groups",
        comodel_name="res.groups",
        relation="scanner_scenario_res_groups_rel",
        column1="scenario_id",
        column2="group_id",
        default=lambda self: [self.env.ref("stock.group_stock_user").id],
    )
    user_ids = fields.Many2many(
        string="Allowed Users",
        comodel_name="res.users",
        relation="scanner_scenario_res_users_rel",
        column1="scenario_id",
        column2="user_id",
    )

    @api.constrains("parent_id")
    def _check_recursion(self):
        if not super(ScannerScenario, self)._check_recursion():
            raise exceptions.UserError(
                _("Error ! You can not create recursive scenarios."),
            )

    def copy(self, default=None):
        default = default or {}
        default["name"] = _("Copy of %s") % self.name

        scenario_new = super(ScannerScenario, self).copy(default)
        step_news = {}
        for step in self.step_ids:
            step_news[step.id] = step.copy({"scenario_id": scenario_new.id}).id
        for trans in self.env["scanner.scenario.transition"].search(
            [("scenario_id", "=", self.id)]
        ):
            trans.copy(
                {
                    "from_id": step_news[trans.from_id.id],
                    "to_id": step_news[trans.to_id.id],
                }
            )
        return scenario_new

    def action_export_scenario(self):
        self.ensure_one()
        return self.env.ref("stock_scanner.action_wizard_export_scenario").read()[0]
