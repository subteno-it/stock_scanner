# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""Data migration helpers: scenarios written for the removed ``tmp_values`` helpers."""

import logging
import re

_logger = logging.getLogger(__name__)

# Calls that cannot be rewritten safely: reported so that they are fixed by hand.
REMOVED_HELPERS = ("set_tmp_value", "update_tmp_values", "clean_tmp_values", "json_tmp_val")

# Replacements of the code shipped with the module (scenario "Login").
SHIPPED_REPLACEMENTS = {
    'terminal.update_tmp_values({"login": message})': (
        'tmp_values = dict(terminal.tmp_values)\ntmp_values["login"] = message\nterminal.tmp_values = tmp_values'
    ),
}


def rewrite_code(code):
    """Replace the removed ``terminal`` helpers that have an exact equivalent.

    ``get_tmp_value(key, default=x)`` becomes ``tmp_values.get(key, x)``.

    Args:
        code: Python code of a step, or condition of a transition.

    Returns:
        str: The rewritten code, unchanged when nothing applies.
    """
    for old, new in SHIPPED_REPLACEMENTS.items():
        code = code.replace(old, new)
    code = code.replace(".get_tmp_value(", ".tmp_values.get(")
    return re.sub(r"(\.tmp_values\.get\([^()\n]*?)default\s*=\s*", r"\1", code)


def migrate_scenario_code(env):
    """Rewrite the steps and transitions that use the removed ``tmp_values`` helpers.

    The migration is idempotent. Code using a helper that has no exact equivalent
    is left untouched and reported in the log.

    Args:
        env: Environment used to read and write the records.

    Returns:
        int: Number of records rewritten.
    """
    rewritten = 0
    for model, field_name in (
        ("scanner.scenario.step", "python_code"),
        ("scanner.scenario.transition", "condition"),
    ):
        records = env[model].with_context(active_test=False).search([])
        for record in records:
            code = record[field_name] or ""
            new_code = rewrite_code(code)
            if new_code != code:
                record[field_name] = new_code
                rewritten += 1
            if any(helper in new_code for helper in REMOVED_HELPERS):
                _logger.warning(
                    "%s %s (scenario %s) still uses a removed tmp_values helper, use terminal.tmp_values instead.",
                    model,
                    record.display_name or record.id,
                    record.scenario_id.display_name,
                )
    return rewritten
