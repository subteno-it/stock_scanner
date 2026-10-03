# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# © 2011 Sylvain Garancher <sylvain.garancher@syleam.fr>

import logging
import sys
import traceback

from odoo import api, exceptions, fields, models

from .common import PYTHON_CODE_DEFAULT

logger = logging.getLogger("stock_scanner")


class ScannerScenarioStep(models.Model):
    """Node of a scenario graph holding the Python code executed when the step is reached."""

    _name = "scanner.scenario.step"
    _description = "Step for scenario"

    # ===========================================================================
    # COLUMNS
    # ===========================================================================
    name = fields.Char(
        string="Name",
        required=False,
        help="Name of the step.",
    )
    scenario_id = fields.Many2one(
        string="Scenario",
        comodel_name="scanner.scenario",
        ondelete="cascade",
        required=True,
        help="Scenario for this step.",
    )
    step_start = fields.Boolean(
        string="Step start",
        default=False,
        help="Check this if this is the first step of the scenario.",
    )
    step_stop = fields.Boolean(
        string="Step stop",
        default=False,
        help="Check this if this is the  last step of the scenario.",
    )
    step_back = fields.Boolean(
        string="Step back",
        default=False,
        help="Check this to stop at this step when returning back.",
    )
    no_back = fields.Boolean(
        string="No back",
        default=False,
        help="Check this to prevent returning back this step.",
    )
    out_transition_ids = fields.One2many(
        string="Outgoing transitions",
        comodel_name="scanner.scenario.transition",
        inverse_name="from_id",
        help="Transitions which goes to this step.",
    )
    in_transition_ids = fields.One2many(
        string="Incoming transitions",
        comodel_name="scanner.scenario.transition",
        inverse_name="to_id",
        help="Transitions which goes to the next step.",
    )
    python_code = fields.Text(
        string="Python code",
        default=PYTHON_CODE_DEFAULT,
        help="Python code to execute.",
    )
    scenario_notes = fields.Text(
        related="scenario_id.notes",
        readonly=False,
    )

    @api.constrains("python_code")
    def _check_python_code_syntax(self):
        """Reject steps whose Python code does not compile, before it fails on a scanner.

        Raises:
            ValidationError: With the line, offset and message of the syntax error.

        Returns:
            bool: Always True when the code is valid.
        """
        for step in self:
            try:
                compile(step.python_code, "<string>", "exec")
            except SyntaxError as exception:
                logger.error(
                    "".join(
                        traceback.format_exception(
                            sys.exc_info()[0],
                            sys.exc_info()[1],
                            sys.exc_info()[2],
                        )
                    )
                )
                raise exceptions.ValidationError(
                    self.env._('Error in python code for step "%s" at line %d, offset %d:\n%s')
                    % (
                        step.name,
                        exception.lineno,
                        exception.offset,
                        exception.msg,
                    )
                ) from exception

        return True
