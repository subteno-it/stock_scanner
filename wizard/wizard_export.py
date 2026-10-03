# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import re
import zipfile
from io import BytesIO

from lxml.etree import Element, SubElement, tostring

from odoo import api, fields, models
from odoo.tools.binary import BinaryBytes


class ExportScenario(models.TransientModel):
    """Export scenarios as a zip of ``.scenario`` XML files and one Python file per step."""

    _name = "wizard.export.scenario"
    _description = "Wizard Export Scenario"

    @api.model
    def default_get(self, fields):
        """Preselect the scenarios the wizard was opened from.

        Args:
            fields: Names of the fields to provide defaults for.

        Returns:
            dict: Default values, with ``scenario_ids`` taken from the active records.
        """
        res = super().default_get(fields)
        if self.env.context.get("active_model") == "scanner.scenario" and self.env.context.get("active_ids"):
            scenario = self.env["scanner.scenario"].browse(self.env.context["active_ids"]).exists()
            res["scenario_ids"] = [(6, 0, scenario.ids)]
        return res

    scenario_ids = fields.Many2many(
        string="Scenario",
        comodel_name="scanner.scenario",
        required=True,
        help="",
    )
    is_copy = fields.Boolean(
        string="Check to make a copy in new instance.",
        default=False,
        help="",
    )
    zip_file = fields.Binary(
        string="Zip File",
        attachment=True,
        help="",
    )

    def action_export(self):  # noqa: C901
        """Build the zip archive of the selected scenarios and return a download action.

        XML-IDs are reused when they exist, otherwise generated from the names (always generated
        when ``is_copy`` is set, so that the export can be loaded as a copy in another instance).
        Duplicated generated XML-IDs get a numeric suffix.

        Returns:
            dict: ``ir.actions.act_url`` action downloading the zip file.
        """
        self.ensure_one()

        def normalize_name(name):
            """Turn a name into a lowercase identifier safe for XML-IDs and file names.

            Args:
                name: Record name.

            Returns:
                str: Name with every non alphanumeric character replaced by an underscore.
            """
            return re.sub(r"[^\w\d]", "_", name).lower()

        def new_node(name, value):
            """Append a text child to the scenario root element.

            Args:
                name: Tag of the new element.
                value: Text content of the element.

            Returns:
                Element: The created element.
            """
            node = SubElement(root, name)
            node.text = value
            return node

        mem_zip = BytesIO()
        zip_filename = "scenario_export.zip"
        zf = zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED)

        for scenario in self.scenario_ids.with_context(active_test=False, lang="en_US"):
            directory = normalize_name(scenario.name)
            scenario_xml_id = scenario.get_metadata()[0]["xmlid"]
            if self.is_copy or not scenario_xml_id:
                scenario_xml_id = f"scenario_{directory}"

            # Add the scenario values in the XML structure
            root = Element("scenario")
            new_node("id", scenario_xml_id)
            new_node("active", str(scenario.active))
            new_node("sequence", str(scenario.sequence))
            new_node("name", scenario.name)
            new_node("type", scenario.type)
            new_node("notes", scenario.notes or "")

            if scenario.model_id:
                (new_node("model_id", scenario.model_id.model),)

            if scenario.company_id:
                (new_node("company_id", scenario.company_id.name),)

            if scenario.parent_id:
                parent_value = scenario.parent_id.get_metadata()[0]["xmlid"]
                if self.is_copy or not parent_value:
                    parent_value = f"scenario_{normalize_name(scenario.parent_id.name)}"
                new_node("parent_id", parent_value)

            for warehouse in scenario.warehouse_ids:
                warehouse_value = warehouse.get_metadata()[0]["xmlid"]
                if not warehouse_value:
                    warehouse_value = warehouse.name
                new_node("warehouse_ids", warehouse_value)

            for user in scenario.user_ids:
                new_node("user_ids", user.login)

            for group in scenario.group_ids:
                group_value = group.get_metadata()[0]["xmlid"]
                if group_value:
                    new_node("group_ids", group_value)

            step_xml_ids = {}

            # Export steps
            transitions = set()
            sorted_steps = sorted(scenario.step_ids, key=lambda record: record.name)
            step_xmlid_counters = {}
            for step in sorted_steps:
                # Retrieve the step's xml ID
                step_xml_id = step.get_metadata()[0]["xmlid"]
                if self.is_copy or not step_xml_id:
                    step_xml_id = f"scenario_step_{directory}_{normalize_name(step.name)}"

                if step_xml_id in step_xmlid_counters:
                    step_xmlid_counters[step_xml_id] += 1
                    step_xml_id += f"_{step_xmlid_counters[step_xml_id]}"
                    step_xmlid_counters[step_xml_id] = 1
                    # This prevents problems with 2 steps
                    # named 'test' [generating 'test'
                    # and 'test_2'] and a third step named 'test_2'
                    # [with this code, it
                    # will generate 'test_2_2']
                else:
                    step_xmlid_counters[step_xml_id] = 1

                step_xml_ids[step.id] = step_xml_id

                # Do not add the scenario name on the python filename
                # if this step is defined in the same module as the scenario
                python_filename = step_xml_id
                if "." in scenario_xml_id and "." in step_xml_id:
                    scenario_module = scenario_xml_id.split(".")[0]
                    step_module = step_xml_id.split(".")[0]
                    if scenario_module == step_module:
                        python_filename = step_xml_id.split(".")[1]
                zf.writestr(
                    zinfo_or_arcname=f"{directory}/{python_filename}.py",
                    data=step.python_code.encode("utf-8"),
                )

                step_attributes = {"id": step_xml_id}
                for field in [
                    "name",
                    "step_start",
                    "step_stop",
                    "step_back",
                    "no_back",
                ]:
                    step_attributes[field] = str(step[field])

                SubElement(root, "Step", attrib=step_attributes)

                # Store the transitions of this step
                transitions.update(step.out_transition_ids)

            # Export transitions
            transition_xmlid_counters = {}
            sorted_transitions = sorted(transitions, key=lambda record: record.name)
            for transition in sorted_transitions:
                # Retrieve the transition's xml ID
                transition_xml_id = transition.get_metadata()[0]["xmlid"]
                if self.is_copy or not transition_xml_id:
                    transition_xml_id = "scenario_transition"
                    f"_{normalize_name(scenario.name)}_{normalize_name(transition.name)}"

                if transition_xml_id in transition_xmlid_counters:
                    transition_xmlid_counters[transition_xml_id] += 1
                    transition_xml_id += f"_{transition_xmlid_counters[transition_xml_id]}"
                    transition_xmlid_counters[transition_xml_id] = 1
                    # This prevents problems with 2 transitions named 'test'
                    # [generating 'test' and 'test_2']
                    # and a third transition named 'test_2' [with
                    # this code, it will generate 'test_2_2']
                else:
                    transition_xmlid_counters[transition_xml_id] = 1

                transition_attributes = {
                    "id": transition_xml_id,
                    "name": transition.name,
                    "sequence": str(transition.sequence),
                    "to_id": step_xml_ids[transition.to_id.id],
                    "from_id": step_xml_ids[transition.from_id.id],
                    "condition": transition.condition,
                    "transition_type": transition.transition_type,
                    # Don't write False in the "tracer" attribute
                    "tracer": transition.tracer or "",
                }
                SubElement(root, "Transition", attrib=transition_attributes)
            xml_filename = f"{directory}.scenario"
            zf.writestr(
                zinfo_or_arcname=f"{directory}/{xml_filename}",
                data=tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True),
            )

        zf.close()
        self.zip_file = BinaryBytes(mem_zip.getvalue(), filename=zip_filename)
        mem_zip.close()

        action = {
            "name": zip_filename,
            "type": "ir.actions.act_url",
            "url": f"web/content/wizard.export.scenario/{self.id}/zip_file/{zip_filename}?download=true",
            "target": "self",
        }
        return action
