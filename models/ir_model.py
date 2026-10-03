# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, models


class IrModelData(models.Model):
    """Make XML-ID based record loading reusable from Python (used by the scenario importer)."""

    _inherit = "ir.model.data"

    @api.model
    def _update(
        self,
        model,
        module,
        values,
        xml_id=False,
        store=True,
        noupdate=False,
        mode="init",
        res_id=False,
    ):
        """Create or update a record through ``_load_records`` instead of the standard XML-ID update.

        Args:
            model: Technical name of the model to load the record into.
            module: Module owning the XML-ID (unused, kept for signature compatibility).
            values: Field values of the record.
            xml_id: Full XML-ID identifying the record.
            store: Unused, kept for signature compatibility.
            noupdate: Whether the XML-ID is flagged noupdate.
            mode: Load mode; anything but "init" is treated as an update.
            res_id: Unused, kept for signature compatibility.
        """
        data = [{"values": values, "xml_id": xml_id, "noupdate": noupdate}]
        self.env[model]._load_records(data, mode != "init")
