# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# © 2015 Sylvain Garancher <sylvain.garancher@syleam.fr>

import logging
import os

from lxml import etree

import odoo
import odoo.modules.loading
from odoo import exceptions
from odoo.tools import misc
from odoo.tools.convert import convert_file
from odoo.tools.safe_eval import safe_eval

logger = logging.getLogger("init:stock_scanner")

ORIGINAL_CONVERT_FILE = convert_file


def get_xml_id(element, module, values):
    """Return the fully qualified XML-ID of a scenario element from its values.

    Args:
        element: Element kind ("scenario", "step", "transition"), used in the error message.
        module: Module used to qualify an XML-ID that has no module prefix.
        values: Element values, holding the XML-ID in ``id`` (or the legacy ``reference_res_id``).

    Returns:
        str: XML-ID in the form ``module.name``.

    Raises:
        UserError: If the element has no id.
    """
    xml_id = values.get("id")
    if not xml_id:
        xml_id = values.get("reference_res_id")
    if not xml_id:
        raise exceptions.UserError(f"The id of a {element} cannot be empty!")

    if "." not in xml_id:
        xml_id = f"{module}.{xml_id}"

    return xml_id


def import_scenario(  # noqa: C901
    env, module, xml_file, mode, directory, filename
):
    """Create or update a scenario, its steps and its transitions from a ``.scenario`` XML file.

    Records are written through ``ir.model.data._update`` so they get XML-IDs and follow the
    module init/update semantics. Step code is read from a Python file next to the XML file.

    Args:
        env: Odoo environment.
        module: Technical name of the module owning the records.
        xml_file: Opened binary file of the ``.scenario`` XML.
        mode: Load mode ("init" or "update").
        directory: Directory containing the scenario file and the step Python files.
        filename: Name of the scenario file (unused, kept for symmetry with the loader).

    Raises:
        ValueError: If a referenced model, company or parent scenario cannot be found.
    """
    model_obj = env["ir.model"]
    company_obj = env["res.company"]
    warehouse_obj = env["stock.warehouse"]
    user_obj = env["res.users"]
    group_obj = env["res.groups"]
    ir_model_data_obj = env["ir.model.data"]

    root = etree.parse(xml_file).getroot()

    steps = []
    transitions = []
    scenario_values = {}
    noupdate = root.get("noupdate", False)

    # parse of the scenario
    for node in root.getchildren():
        # the node of the Step and Transition are put in other list
        if node.tag == "Step":
            steps.append(node)
        elif node.tag == "Transition":
            transitions.append(node)
        elif node.tag == "warehouse_ids":
            if "warehouse_ids" not in scenario_values:
                scenario_values["warehouse_ids"] = []
            warehouse_ids = warehouse_obj.search([("name", "=", node.text)])
            if warehouse_ids:
                scenario_values["warehouse_ids"].append((4, warehouse_ids[0].id))
        elif node.tag == "group_ids":
            if "group_ids" not in scenario_values:
                scenario_values["group_ids"] = []

            group_ids = group_obj.search([
                ("full_name", "=", node.text),
            ])
            if group_ids:
                scenario_values["group_ids"].append((4, group_ids[0].id))
            else:
                scenario_values["group_ids"].append(
                    (4, env.ref(node.text).id),
                )
        elif node.tag == "user_ids":
            if "user_ids" not in scenario_values:
                scenario_values["user_ids"] = []

            user_ids = user_obj.search([
                ("login", "=", node.text),
            ])
            if user_ids:
                scenario_values["user_ids"].append((4, user_ids[0].id))
        elif node.tag == "active":
            scenario_values[node.tag] = safe_eval(node.text) or False
        else:
            scenario_values[node.tag] = node.text or False

    # Transition from old format to new format
    scenario_xml_id = get_xml_id("scenario", module, scenario_values)

    if scenario_values["model_id"]:
        scenario_values["model_id"] = (
            model_obj.search([
                ("model", "=", scenario_values["model_id"]),
            ]).id
            or False
        )
        if not scenario_values["model_id"]:
            raise ValueError("Model not found: {}".format(scenario_values["model_id"]))

    if scenario_values.get("company_id"):
        scenario_values["company_id"] = (
            company_obj.search([
                ("name", "=", scenario_values["company_id"]),
            ]).id
            or False
        )
        if not scenario_values["company_id"]:
            raise ValueError("Company not found: {}".format(scenario_values["company_id"]))

    if scenario_values.get("parent_id"):
        if "." not in scenario_values["parent_id"]:
            scenario_values["parent_id"] = "{}.{}".format(
                module,
                scenario_values["parent_id"],
            )
        parent_scenario = env.ref(scenario_values["parent_id"], raise_if_not_found=False)
        if not parent_scenario:
            raise ValueError("Parent scenario not found: {}".format(scenario_values["parent_id"]))

        scenario_values["parent_id"] = parent_scenario.id

    # Create or update the scenario
    ir_model_data_obj._update(
        "scanner.scenario",
        module,
        scenario_values,
        xml_id=scenario_xml_id,
        mode=mode,
        noupdate=noupdate,
    )
    scenario = env.ref(scenario_xml_id)

    # Create or update steps
    resid = {}
    for node in steps:
        step_values = {}
        for key, item in node.items():
            if item == "False":
                item = False
            step_values[key] = item

        # Get scenario id
        step_values["scenario_id"] = scenario.id

        # Transition from old to new format
        step_xml_id = get_xml_id("step", module, step_values)

        # Get python source
        python_filename = f"{directory}/{step_xml_id}.py"
        # Alow to use the id without module name for the current module
        try:
            python_file = misc.file_open(python_filename)
        except OSError:
            if module == step_xml_id.split(".")[0]:
                python_filename = "{}/{}.py".format(directory, step_xml_id.split(".")[1])
                python_file = misc.file_open(python_filename)

        # Load python code and check syntax
        try:
            step_values["python_code"] = python_file.read()

        finally:
            python_file.close()

        # Create or update
        ir_model_data_obj._update(
            "scanner.scenario.step",
            module,
            step_values,
            xml_id=step_xml_id,
            mode=mode,
            noupdate=noupdate,
        )
        step = env.ref(step_xml_id)
        resid[step_xml_id] = step.id

    # Create or update transitions
    for node in transitions:
        transition_values = {}
        for key, item in node.items():
            if key in ["to_id", "from_id"]:
                item = resid[get_xml_id("step", module, {"id": item})]

            transition_values[key] = item

        # Create or update
        ir_model_data_obj._update(
            "scanner.scenario.transition",
            module,
            transition_values,
            xml_id=get_xml_id("transition", module, transition_values),
            mode=mode,
            noupdate=noupdate,
        )


def scenario_convert_file(
    env,
    module,
    filename,
    idref,
    mode="update",
    noupdate=False,
    kind=None,
    pathname=None,
):
    """Replacement of ``convert_file`` that also loads ``.scenario`` files declared in manifests.

    Any other file type is delegated to the original Odoo implementation.

    Args:
        env: Odoo environment.
        module: Technical name of the module being loaded.
        filename: File path relative to the module.
        idref: Mapping of XML-IDs to ids, forwarded to the original loader.
        mode: Load mode ("init" or "update").
        noupdate: Whether records are flagged noupdate (forwarded to the original loader).
        kind: Kind of data file (forwarded to the original loader).
        pathname: Full path of the file; computed from module and filename when omitted.
    """
    if pathname is None:
        pathname = os.path.join(module, filename)

    directory, filename = os.path.split(pathname)
    extension = os.path.splitext(filename)[1].lower()
    if extension == ".scenario":
        with misc.file_open(pathname, "rb", env=env) as fp:
            import_scenario(env, module, fp, mode, directory, filename)
    else:
        ORIGINAL_CONVERT_FILE(
            env,
            module,
            filename,
            idref,
            mode=mode,
            noupdate=noupdate,
            kind=kind,
            pathname=pathname,
        )


# Monkey patch Odoo's module file loading
# To be able to load scenarios from manifest file
odoo.tools.convert_file = scenario_convert_file
odoo.tools.convert.convert_file = scenario_convert_file
odoo.modules.loading.convert_file = scenario_convert_file
