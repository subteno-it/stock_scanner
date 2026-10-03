# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# © 2011 Sylvain Garancher <sylvain.garancher@syleam.fr>

import logging
import sys
import traceback

from odoo import api, exceptions, fields, models

logger = logging.getLogger("stock_scanner")


class ScannerScenarioTransition(models.Model):
    """Edge between two steps of a scenario, followed when its condition evaluates to True."""

    _name = "scanner.scenario.transition"
    _description = "Transition for scenario"
    _order = "sequence"

    @api.model
    def _transition_type_get(self):
        """Return the selectable transition types.

        Returns:
            list: Selection tuples (value, label).
        """
        return [
            ("scanner", "Scanner"),
            ("keyboard", "Keyboard"),
        ]

    # ===========================================================================
    # COLUMNS
    # ===========================================================================
    name = fields.Char(
        string="Name",
        required=True,
        help="Name of the transition.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=0,
        required=False,
        help="Sequence order.",
    )
    from_id = fields.Many2one(
        string="From",
        comodel_name="scanner.scenario.step",
        ondelete="cascade",
        required=True,
        help="Step which launches this transition.",
    )
    to_id = fields.Many2one(
        string="To",
        comodel_name="scanner.scenario.step",
        ondelete="cascade",
        required=True,
        help="Step which is reached by this transition.",
    )
    condition = fields.Char(
        string="Condition",
        default="True",
        required=True,
        help="The transition is followed only if this condition is evaluated as True.",
    )
    transition_type = fields.Selection(
        string="Transition Type",
        selection="_transition_type_get",
        default="keyboard",
        help="Type of transition.",
    )
    tracer = fields.Char(
        string="Tracer",
        default=False,
        required=False,
        help="Used to determine fron which transition we arrive to the destination step.",
    )
    scenario_id = fields.Many2one(
        string="Scenario",
        related="from_id.scenario_id",
        comodel_name="scanner.scenario",
        ondelete="cascade",
        required=False,
        store=True,
        readonly=True,
    )

    @api.constrains("from_id", "to_id")
    def _check_scenario(self):
        """Ensure both ends of the transition belong to the same scenario.

        Raises:
            ValidationError: If the source and destination steps are in different scenarios.

        Returns:
            bool: Always True when valid.
        """
        if self.from_id.scenario_id.id != self.to_id.scenario_id.id:
            raise exceptions.ValidationError(
                self.env._("Error ! You can not create recursive scenarios."),
            )

        return True

    @api.constrains("condition")
    def _check_condition_syntax(self):
        """Reject transitions whose condition is not a valid Python expression.

        Raises:
            ValidationError: With the line, offset and message of the syntax error.

        Returns:
            bool: Always True when the condition is valid.
        """
        for transition in self:
            try:
                compile(transition.condition, "<string>", "eval")
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
                    self.env._('Error in condition for transition "%s" at line %d, offset %d:\n%s')
                    % (
                        transition.name,
                        exception.lineno,
                        exception.offset,
                        exception.msg,
                    )
                ) from exception

        return True
