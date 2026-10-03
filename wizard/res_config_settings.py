# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# © 2015 Laurent Mignon <laurent.mignon@acsone.eu>

from odoo import fields, models

ACTIVABLE_XML_IDS = [
    "stock_scanner.hardware_reset_user_id_on_timeout",
    "stock_scanner.scanner_scenario_login",
    "stock_scanner.scanner_scenario_logout",
]


class StockConfig(models.TransientModel):
    """Add settings to enable the scanner login/logout scenarios and set the session timeout."""

    _inherit = "res.config.settings"

    is_login_enabled = fields.Boolean(
        string="Is Login Enabled",
        help="",
    )
    session_timeout_delay = fields.Integer(
        string="Session Timeout Delay",
        help="",
    )

    def get_values(self):
        """Read the login toggle and session timeout from the shipped scenario/parameter records.

        Returns:
            dict: Standard settings values completed with the scanner ones.
        """
        values = super().get_values()
        is_login_enabled = self.env.ref(ACTIVABLE_XML_IDS[0]).active
        session_timeout_delay = self.env.ref("stock_scanner.hardware_scanner_session_timeout_sec").value

        values.update(
            is_login_enabled=is_login_enabled,
            session_timeout_delay=int(session_timeout_delay),
        )

        return values

    def set_values(self):
        """Activate or deactivate the login-related records and store the session timeout.

        Returns:
            Result of the parent ``set_values``.
        """
        res = super().set_values()
        for xml_id in ACTIVABLE_XML_IDS:
            self.env.ref(xml_id).active = self.is_login_enabled

        self.env["ir.config_parameter"].set_int("hardware_scanner_session_timeout", self.session_timeout_delay)

        return res
