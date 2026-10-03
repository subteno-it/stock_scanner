# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""Rewrite the scenarios using the tmp_values helpers removed from scanner.hardware.

The shipped Login scenario is loaded with noupdate, so a database coming from
19.0 keeps the old code, which would fail once the helpers are gone.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.stock_scanner.migration import migrate_scenario_code


def migrate(cr, version):
    """Rewrite the step code and transition conditions using the removed helpers.

    Args:
        cr: Database cursor.
        version: Previously installed version of the module.
    """
    migrate_scenario_code(api.Environment(cr, SUPERUSER_ID, {}))
