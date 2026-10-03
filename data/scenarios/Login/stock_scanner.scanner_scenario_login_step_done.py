# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# flake8: noqa
"Use <m> or <message> to retrieve the data transmitted by the scanner."

# Use <t> or <terminal> to retrieve the running terminal browse record.
# Put the returned action code in <act>, as a single character.
# Put the returned result or message in <res>, as a list of strings.
# Put the returned value in <val>, as an integer

terminal.login(terminal.tmp_values.get("login"), message)

act = "F"
res = [
    _("You are now authenticated as %s !") % terminal.tmp_values.get("login"),
]
