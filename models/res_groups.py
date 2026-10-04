# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import models


class ResGroups(models.Model):
    """Declare the group of the technical user of the scanners as light."""

    _inherit = "res.groups"

    def _get_light_group_xmlids(self):
        """Add the group of the technical user to the light groups.

        A user of the sentinel group only answers the calls of the terminals: the scenarios run with the rights of the
        operator logged in on the terminal. Such a user can be a light user, which costs less than a regular one.

        Returns:
            tuple: The XML IDs of the light groups.
        """
        return (
            *super()._get_light_group_xmlids(),
            "stock_scanner.group_stock_scanner_sentinel",
        )
