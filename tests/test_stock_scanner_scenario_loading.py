# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Copyright 2017 SYLEAM Info Services

from odoo import exceptions
from odoo.tests import common, tagged
from odoo.tools.convert import convert_file

from ..load_scenario import get_xml_id


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerScenarioLoading(common.TransactionCase):
    """Cover XML id resolution and error handling when loading scenario files."""

    def test_get_xml_id_from_id(self):
        """An explicit id takes priority over the reference_res_id and is prefixed with the module."""
        xml_id = get_xml_id(
            "element",
            "stock_scanner",
            {
                "id": "the_id",
                # Add the two values in order to check the priority
                "reference_res_id": "other_id",
            },
        )
        self.assertEqual(xml_id, "stock_scanner.the_id")

    def test_get_xml_id_from_reference_res_id(self):
        """Without an id, the reference_res_id is used and prefixed with the module."""
        xml_id = get_xml_id(
            "element",
            "stock_scanner",
            {
                "reference_res_id": "other_id",
            },
        )
        self.assertEqual(xml_id, "stock_scanner.other_id")

    def test_get_xml_id_from_full_id(self):
        """An id already containing a module name is returned unchanged."""
        xml_id = get_xml_id(
            "element",
            "stock_scanner",
            {
                "id": "module_name.the_id",
                # Add the two values in order to check the priority
                "reference_res_id": "other_id",
            },
        )
        self.assertEqual(xml_id, "module_name.the_id")

    def test_get_xml_id_from_full_reference_res_id(self):
        """A reference_res_id already containing a module name is returned unchanged."""
        xml_id = get_xml_id(
            "element",
            "stock_scanner",
            {
                "reference_res_id": "module_name.other_id",
            },
        )
        self.assertEqual(xml_id, "module_name.other_id")

    def test_get_xml_id_without_value(self):
        """Resolving an xml id without id nor reference_res_id must raise a UserError."""
        with self.assertRaises(exceptions.UserError):
            get_xml_id("element", "stock_scanner", {})

    def test_wrong_model(self):
        """Loading a scenario file with an unknown model must raise a ValueError."""
        with self.assertRaises(ValueError):
            convert_file(
                self.env,
                "stock_scanner",
                "tests/data/TestWrongModel.scenario",
                {},
            )

    def test_wrong_company(self):
        """Loading a scenario file with an unknown company must raise a ValueError."""
        with self.assertRaises(ValueError):
            convert_file(
                self.env,
                "stock_scanner",
                "tests/data/TestWrongCompany.scenario",
                {},
            )

    def test_wrong_parent_scenario(self):
        """Loading a scenario file with an unknown parent scenario must raise a ValueError."""
        with self.assertRaises(ValueError):
            convert_file(
                self.env,
                "stock_scanner",
                "tests/data/TestWrongParent.scenario",
                {},
            )
