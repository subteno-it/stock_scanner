# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# flake8: noqa
"Use <m> or <message> to retrieve the data transmitted by the scanner."

# Use <t> or <terminal> to retrieve the running terminal browse record.
# Put the returned action code in <act>, as a single character.
# Put the returned result or message in <res>, as a list of strings.
# Put the returned value in <val>, as an integer

tmp_values = dict(terminal.tmp_values)
tmp_values["login"] = message
terminal.tmp_values = tmp_values

act = "T"
res = [
    _("| Login %s") % message,
    _("Pwd ?"),
]
