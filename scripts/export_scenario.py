#!/usr/bin/env python3
# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# © 2011 Christophe CHAUVET <christophe.chauvet@syleam.fr>
# © 2011 Jean-Sébastien SUZANNE <jean-sebastien.suzanne@syleam.fr>
# © 2015 Sylvain Garancher <sylvain.garancher@syleam.fr>
# © 2018 Chris Tribbeck <chris.tribbeck@subteno-it.fr>
"""Export a scenario of the stock_scanner module to a directory, through the JSON-2 API.

The export is done on the server by the "wizard.export.scenario" wizard, the same one
as the "Export" button of the scenario form. This script only calls it and unpacks
the resulting zip file, so the result is always the one of the module itself.

Requires the ``odoo-sentinel-json2`` package and an API key of a user allowed to read the scenarios.
"""

import argparse
import base64
import io
import logging
import os
import sys
import zipfile

try:
    from odoo_sentinel_json2.client import ODOO, Json2Error
except ImportError:
    sys.exit("This script requires the odoo-sentinel-json2 package: uv pip install odoo-sentinel-json2")

logger = logging.getLogger("Export scenario")

WIZARD = "wizard.export.scenario"


def parse_arguments(argv):
    """Parse the command line.

    Args:
        argv: Arguments, without the program name.

    Returns:
        argparse.Namespace: The parsed options.
    """
    parser = argparse.ArgumentParser(
        description="Scenarios export script for Odoo's stock_scanner module",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    connection_group = parser.add_argument_group("Connection")
    connection_group.add_argument("--host", default="localhost", help="Address of the Odoo server.")
    connection_group.add_argument("-p", "--port", type=int, default=8069, help="Port of the Odoo server.")
    connection_group.add_argument("--ssl", action="store_true", help="Use https.")
    connection_group.add_argument("-d", "--database", help="Database of the scenario (optional with one database).")
    connection_group.add_argument(
        "-k",
        "--api-key",
        dest="api_key",
        default=os.environ.get("ODOO_API_KEY"),
        help="API key of the exporting user. Defaults to the ODOO_API_KEY environment variable.",
    )
    export_group = parser.add_argument_group("Export")
    export_group.add_argument("-v", "--verbose", action="store_true", help="Run in verbose mode.")
    export_group.add_argument("-i", "--id", dest="scenario_id", required=True, type=int, help="ID of the scenario.")
    export_group.add_argument("-n", "--name", help="Name of the exported .scenario file.")
    export_group.add_argument("--directory", default=".", help="Directory where to write the exported scenario.")
    export_group.add_argument(
        "--copy",
        action="store_true",
        help="Export as a copy for a new instance: generate new XML ids instead of the existing ones.",
    )
    return parser.parse_args(argv)


def fetch_export(connection, scenario_id, is_copy=False):
    """Run the export wizard on the server and return its zip file.

    Args:
        connection: Connected ``odoo_sentinel_json2.client.ODOO``.
        scenario_id: ID of the scenario to export.
        is_copy: Generate new XML ids, as for a copy in another instance.

    Returns:
        bytes: Content of the zip file.
    """
    (wizard_id,) = connection.call(
        WIZARD,
        "create",
        vals_list=[{"scenario_ids": [[6, 0, [scenario_id]]], "is_copy": is_copy}],
    )
    try:
        connection.call(WIZARD, "action_export", ids=[wizard_id])
        (record,) = connection.call(WIZARD, "read", ids=[wizard_id], fields=["zip_file"])
    finally:
        connection.call(WIZARD, "unlink", ids=[wizard_id])
    zip_file = record["zip_file"]
    if isinstance(zip_file, dict):
        zip_file = zip_file.get("content")
    if not zip_file:
        raise Json2Error(f"The server returned no export for the scenario {scenario_id}")
    return base64.b64decode(zip_file)


def write_export(content, directory, name=None):
    """Unpack an exported scenario into a directory.

    The zip file holds a folder with the ``.scenario`` file and one ``.py`` file per step. Files are
    written flat in ``directory``, and the ``.scenario`` file is named after ``name``, or after the
    directory when no name is given.

    Args:
        content: Content of the zip file.
        directory: Destination directory, created if needed.
        name: Name of the ``.scenario`` file, without extension.

    Returns:
        list: Paths of the written files.
    """
    directory = os.path.expanduser(directory)
    os.makedirs(directory, exist_ok=True)
    scenario_name = name or os.path.basename(os.path.abspath(directory))
    written = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            # Only the file name is kept: never write outside of the directory
            filename = os.path.basename(member.filename)
            if filename.endswith(".scenario"):
                filename = f"{scenario_name}.scenario"
            path = os.path.join(directory, filename)
            with open(path, "wb") as destination:
                destination.write(archive.read(member))
            written.append(path)
    return written


def main(argv=None):
    """Export the scenario given on the command line.

    Args:
        argv: Arguments, defaults to ``sys.argv[1:]``.

    Returns:
        int: Exit status.
    """
    options = parse_arguments(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if options.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    if not options.api_key:
        logger.error("An API key is required: use --api-key or the ODOO_API_KEY environment variable")
        return 1
    try:
        logger.info('Open connection to "%s:%s"', options.host, options.port)
        connection = ODOO(
            options.host,
            port=options.port,
            protocol="https" if options.ssl else "http",
            database=options.database,
            api_key=options.api_key,
        )
        content = fetch_export(connection, options.scenario_id, options.copy)
    except (Json2Error, ValueError) as error:
        logger.error("Export failed: %s", error)
        return 1
    for path in write_export(content, options.directory, options.name):
        logger.info("Written %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
