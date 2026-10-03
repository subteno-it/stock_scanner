# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# © 2015 Sylvain Garancher <sylvain.garancher@syleam.fr>

from odoo import fields, models


class ScannerHardwareStepHistory(models.Model):
    """Steps executed by a terminal during its current scenario, used to go back to a previous step."""

    _name = "scanner.hardware.step.history"
    _description = "Steps History of Scanner Hardware"
    _order = "id"

    hardware_id = fields.Many2one(
        string="Hardware",
        comodel_name="scanner.hardware",
        required=True,
        help="Hardware linked to this history line.",
    )
    step_id = fields.Many2one(
        string="Step",
        comodel_name="scanner.scenario.step",
        help="Step executed during this history line.",
    )
    transition_id = fields.Many2one(
        string="Transition",
        comodel_name="scanner.scenario.transition",
        help="Transition executed during this history line.",
    )
    message = fields.Char(
        string="Message",
        help="Message sent during execution of the step.",
    )
