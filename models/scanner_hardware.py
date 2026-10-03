# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# © 2011 Sylvain Garancher <sylvain.garancher@syleam.fr>

import datetime
import logging
import random
import time

from psycopg2 import OperationalError, errorcodes

from odoo import api, exceptions, fields, models
from odoo.tools.misc import html_escape
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import get_translation

_logger = logging.getLogger("stock_scanner")

_CURSES_COLORS_VALUES = [
    "black",
    "blue",
    "cyan",
    "green",
    "magenta",
    "red",
    "white",
    "yellow",
]

PG_CONCURRENCY_ERRORS_TO_RETRY = (
    errorcodes.LOCK_NOT_AVAILABLE,
    errorcodes.SERIALIZATION_FAILURE,
    errorcodes.DEADLOCK_DETECTED,
)
MAX_TRIES_ON_CONCURRENCY_FAILURE = 5


class ScannerHardware(models.Model):
    """Physical or virtual barcode terminal, holding its running scenario, current step and temporary values."""

    _name = "scanner.hardware"
    _description = "Scanner Hardware"

    @api.model
    def _colors_get(self):
        """Return the selectable terminal colors with translated labels.

        Returns:
            list: Selection tuples (curses color name, label).
        """
        return [
            ("black", self.env._("Black")),
            ("blue", self.env._("Blue")),
            ("cyan", self.env._("Cyan")),
            ("green", self.env._("Green")),
            ("magenta", self.env._("Magenta")),
            ("red", self.env._("Red")),
            ("white", self.env._("White")),
            ("yellow", self.env._("Yellow")),
        ]

    # ===========================================================================
    # COLUMNS
    # ===========================================================================
    name = fields.Char(
        string="Name",
        required=True,
        help="The name of the hardware.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="",
    )
    code = fields.Char(
        string="Code",
        required=True,
        help="The code of this hardware.",
    )
    log_enabled = fields.Boolean(
        string="Log enabled",
        default=False,
        help="Enable logging messages from scenarios.",
    )
    screen_width = fields.Integer(
        string="Screen Width",
        default=20,
        required=False,
        help="Width of the terminal's screen.",
    )
    screen_height = fields.Integer(
        string="Screen Height",
        default=4,
        help="Height of the terminal's screen.",
    )
    warehouse_id = fields.Many2one(
        string="Warehouse",
        comodel_name="stock.warehouse",
        ondelete="restrict",
        required=True,
        help="Warehouse where is located this hardware.",
    )
    user_id = fields.Many2one(
        string="User",
        comodel_name="res.users",
        ondelete="restrict",
        help="Allow to define an other user for execute all scenarios with that scanner instead of default user.",
    )
    last_call_dt = fields.Datetime(
        string="Last call",
        help="Date and time of the last call to the system done by the scanner.",
    )
    scenario_id = fields.Many2one(
        string="Scenario",
        comodel_name="scanner.scenario",
        ondelete="restrict",
        readonly=True,
        help="Scenario used for this hardware.",
    )
    step_id = fields.Many2one(
        string="Current Step",
        comodel_name="scanner.scenario.step",
        ondelete="restrict",
        readonly=True,
        help="Current step for this hardware.",
    )
    step_history_ids = fields.One2many(
        string="Steps History",
        comodel_name="scanner.hardware.step.history",
        inverse_name="hardware_id",
        readonly=True,
        help="History of all steps executed by this hardware during the current scenario.",
    )
    reference_document = fields.Integer(
        string="Reference",
        readonly=True,
        help="ID of the reference document.",
    )
    base_fg_color = fields.Selection(
        string="Base - Text Color",
        selection="_colors_get",
        default="white",
        required=True,
        help="Default color for the text.",
    )
    base_bg_color = fields.Selection(
        string="Base - Background Color",
        selection="_colors_get",
        default="blue",
        required=True,
        help="Default color for the background.",
    )
    info_fg_color = fields.Selection(
        string="Info - Text Color",
        selection="_colors_get",
        default="yellow",
        required=True,
        help="Color for the info text.",
    )
    info_bg_color = fields.Selection(
        string="Info - Background Color",
        selection="_colors_get",
        default="blue",
        required=True,
        help="Color for the info background.",
    )
    error_fg_color = fields.Selection(
        string="Error - Text Color",
        selection="_colors_get",
        default="yellow",
        required=True,
        help="Color for the error text.",
    )
    error_bg_color = fields.Selection(
        string="Error - Background Color",
        selection="_colors_get",
        default="red",
        required=True,
        help="Color for the error background.",
    )
    tmp_values = fields.Serialized(
        string="Tmp Values",
        readonly=True,
        help="",
    )
    tmp_values_display = fields.Html(
        string="Tmp Values Display",
        compute="_compute_tmp_values_display",
        help="Debug tmp values",
    )

    @api.depends("tmp_values")
    def _compute_tmp_values_display(self):
        """Render the temporary values as an HTML table so they can be inspected on the form."""
        for rec in self:
            txt = [
                "<table><tr>",
                "<th>" + html_escape(self.env._("Key")) + "</th>",
                "<th>" + html_escape(self.env._("Value")) + "</th></tr>",
            ]
            for key in sorted(rec.tmp_values.keys()):
                val = rec.tmp_values[key]
                txt.append(f"<tr><td>{html_escape(key)}</td><td>{html_escape(val)}</td></tr>")
            txt.append("</table>")
            rec.tmp_values_display = "".join(txt)

    @api.model
    def timeout_session(self):
        """Log out and reset terminals whose last call is older than the session timeout.

        Meant to be run by a cron. The delay comes from the ``hardware_scanner_session_timeout`` parameter
        (seconds, 1800 by default).
        """
        timeout_delay = self.env["ir.config_parameter"].get_int("hardware_scanner_session_timeout", 1800)  # seconds
        expired_dt = datetime.datetime.now() - datetime.timedelta(seconds=timeout_delay)
        expired_str = fields.Datetime.to_string(expired_dt)
        terminals = self.search([("last_call_dt", "<", expired_str)])
        if terminals:
            terminals.logout()
            terminals.empty_scanner_values()

    @api.model
    def _get_terminal(self, terminal_number):
        """Find the terminal matching a code.

        Args:
            terminal_number: Code of the terminal.

        Returns:
            recordset: The single matching terminal.

        Raises:
            ValueError: If no terminal or several terminals match.
        """
        terminal = self.search([("code", "=", terminal_number)])
        terminal.ensure_one()
        return terminal

    @api.model
    def scanner_check(self, terminal_number):
        """Tell the terminal whether a scenario is already running, e.g. to resume after a disconnection.

        Args:
            terminal_number: Code of the terminal.

        Returns:
            tuple | bool: (scenario id, scenario name) of the running scenario, False when there is none.
        """
        terminal = self._get_terminal(terminal_number)
        uid = terminal.user_id.id or self.env.uid
        terminal = terminal.with_user(uid)
        return terminal.scenario_id and (terminal.scenario_id.id, terminal.scenario_id.name) or False

    @api.model
    def scanner_call(self, terminal_number, action, message=False, transition_type="keyboard"):
        """Entry point called by the barcode reader for every user interaction.

        The call is executed as the user assigned to the terminal (after login), otherwise as the current user.
        The terminal protocol answer is a tuple (action code, list of message lines, value), for example
        ``("M", ["text"], 0)``.

        Args:
            terminal_number: Code of the terminal.
            action: Requested action ("screen_size", "screen_colors", "action", "restart", "back" or "end").
            message: Text typed or scanned on the terminal.
            transition_type: Origin of the input, "keyboard" or "scanner".

        Returns:
            tuple: (action code, message lines, value) to display on the terminal.
        """
        # Retrieve the terminal id
        terminal = self._get_terminal(terminal_number)
        if terminal.user_id.id:
            # only reset last call if user_id
            terminal.last_call_dt = fields.Datetime.now()
        # Change uid if defined on the stock scanner
        uid = terminal.user_id.id or self.env.uid
        return terminal.with_user(uid)._scanner_call(action, message=message, transition_type=transition_type)

    def _scanner_call(self, action, message=False, transition_type="keyboard"):
        """Dispatch a terminal request, once the terminal and the user have been resolved.

        Args:
            action: Requested action, see ``scanner_call``.
            message: Text typed or scanned on the terminal.
            transition_type: Origin of the input, "keyboard" or "scanner".

        Returns:
            tuple: (action code, message lines, value); "L" lists menu entries, "F" ends the scenario, "R"/"U"
            report an error or an unknown action.
        """
        self.ensure_one()
        scanner_scenario_obj = self.env["scanner.scenario"]
        # Retrieve the terminal screen size
        if action == "screen_size":
            _logger.debug("Retrieve screen size")
            screen_size = self._screen_size()
            return ("M", screen_size, 0)

        # Retrieve the terminal screen colors
        if action == "screen_colors":
            _logger.debug("Retrieve screen colors")
            screen_colors = {
                "base": (self.base_fg_color, self.base_bg_color),
                "info": (self.info_fg_color, self.info_bg_color),
                "error": (self.error_fg_color, self.error_bg_color),
            }
            return ("M", screen_colors, 0)

        # Execute the action
        elif action == "action":
            # The terminal is attached to a scenario
            if self.scenario_id:
                return self._scenario_save(
                    message,
                    transition_type,
                    scenario_id=self.scenario_id.id,
                    step_id=self.step_id.id,
                )
            # We asked for a scan transition type, but no action is running,
            # forbidden
            elif transition_type == "scanner":
                return self._unknown_action(message)
            # No action to do
            else:
                _logger.info("[%s] Action : %s (no current scenario)", self.code, message)
                scenario_ids = scanner_scenario_obj.search([
                    ("name", "=", message),
                    ("type", "=", "menu"),
                    "|",
                    ("warehouse_ids", "=", False),
                    ("warehouse_ids", "in", [self.warehouse_id.id]),
                ])
                if scenario_ids:
                    scenarios = self._scenario_list(parent_id=scenario_ids.id)
                    if scenarios:
                        menu_name = scenario_ids[0].name
                        return ("L", [f"|{menu_name}"] + scenarios, 0)
                return self._scenario_save(message, transition_type)

        # Reload current step
        elif action == "restart":
            # The terminal is attached to a scenario
            if self.scenario_id:
                return self._scenario_save(
                    message,
                    "restart",
                    scenario_id=self.scenario_id.id,
                    step_id=self.step_id.id,
                )

        # Reload previous step
        elif action == "back":
            # The terminal is attached to a scenario
            if self.scenario_id:
                return self._scenario_save(
                    message,
                    "back",
                    scenario_id=self.scenario_id.id,
                    step_id=self.step_id.id,
                )

        # End required
        elif action == "end":
            # Empty the values
            _logger.info(f"[{self.code}] End scenario request")
            self.sudo().empty_scanner_values()

            return ("F", [self.env._("This scenario"), self.env._("is finished")], "")

        # If the terminal is not attached to a scenario, send the menu
        # (scenario list)
        if not self.scenario_id:
            _logger.info(f"[{self.code}] No running scenario")
            scenarios = self._scenario_list(message)
            return ("L", scenarios, 0)

        # Nothing matched, return an error
        return self._send_error(["Unknown action"])

    def _send_error(self, message):
        """Reset the terminal and build an error answer, so that the user restarts from the menu.

        Args:
            message: Lines to display.

        Returns:
            tuple: ("R", message, 0).
        """
        self.ensure_one()
        self.sudo().empty_scanner_values()
        return ("R", message, 0)

    @api.model
    def _unknown_action(self, message):
        """Build the answer for an action that cannot be handled in the current state.

        Args:
            message: Lines to display.

        Returns:
            tuple: ("U", message, 0).
        """
        return ("U", message, 0)

    def empty_scanner_values(self):
        """Reset the scenario, step, history, reference document and temporary values of the terminal.

        The ORM is used on purpose (not SQL), since SQL resets are discouraged in production.

        Returns:
            bool: Always True.
        """
        self.write({
            "scenario_id": False,
            "step_id": False,
            "step_history_ids": [(2, history.id) for history in self.step_history_ids],
            "reference_document": 0,
            "tmp_values": {},
        })
        return True

    @api.model
    def scanner_end(self, numterm=None):
        """Run the "end" action, called when the end barcode is read.

        Args:
            numterm: Code of the terminal.

        Returns:
            tuple: Terminal protocol answer, ("F", lines, "") when the scenario is finished.
        """
        return self.scanner_call(terminal_number=numterm, action="end")

    @api.model
    def check_credentials(self, login, password):
        """Check a login and password without opening an interactive session.

        Args:
            login: Login of the user.
            password: Password of the user.

        Returns:
            int | bool: Id of the user when the credentials are valid, False when access is denied. An unknown
            login returns the empty user id (falsy).
        """
        res_users = self.env["res.users"]
        try:
            # Sentinel technical users cannot read res.users, as in res.users._login
            user = res_users.sudo().search([("login", "=", login)], limit=1)
            if user:
                user.with_user(user).sudo()._check_credentials(
                    {"type": "password", "login": login, "password": password},
                    {"interactive": False},
                )
            return user.id
        except exceptions.AccessDenied:
            return False

    def login(self, login, password):
        """Assign the user matching the credentials as the user of the terminal.

        It MUST be called on the last step of the login scenario, since that scenario is no longer visible
        by the current user once the new user is assigned.

        Args:
            login: Login of the user.
            password: Password of the user.
        """
        self.ensure_one()
        uid = self.check_credentials(login, password)
        if uid:
            self.write({
                "user_id": uid,
                "last_call_dt": fields.Datetime.now(),
            })

    def logout(self):
        """Detach the user from the terminal.

        Returns:
            bool: Always True.
        """
        self.write({
            "user_id": False,
            "last_call_dt": False,
        })
        return True

    def _memorize(self, scenario_id, step_id, obj=None):
        """Store the scenario and step the terminal is running.

        Args:
            scenario_id: Id of the running scenario.
            step_id: Id of the current step.
            obj: Unused, kept for compatibility.
        """
        self.ensure_one()
        self.write({
            "scenario_id": scenario_id,
            "step_id": step_id,
        })

    def _get_step_translation_module(self, step):
        """Find the module whose translations apply to the code of a step.

        The module of the step XML-ID is preferred, then the one of its scenario.

        Args:
            step: Step being executed.

        Returns:
            str | None: Technical name of the module, None when neither has an XML-ID.
        """
        self.ensure_one()
        imd_obj = self.env["ir.model.data"].sudo()

        step_xmlid = imd_obj.search(
            [
                ("model", "=", "scanner.scenario.step"),
                ("res_id", "=", step.id),
            ],
            limit=1,
        )
        if step_xmlid and step_xmlid.module:
            return step_xmlid.module

        scenario_xmlid = imd_obj.search(
            [
                ("model", "=", "scanner.scenario"),
                ("res_id", "=", step.scenario_id.id),
            ],
            limit=1,
        )
        if scenario_xmlid and scenario_xmlid.module:
            return scenario_xmlid.module

        return None

    def _build_step_translator(self, step):
        """Build the ``_()`` function exposed to step code, which is run through ``exec`` and so cannot use the
        standard translation machinery.

        Args:
            step: Step being executed.

        Returns:
            callable: Function translating a source string and interpolating positional or keyword arguments.
            A badly formatted translation falls back to the source string and is logged.
        """
        module = self._get_step_translation_module(step)
        lang = self.env.context.get("lang") or self.env.lang or self.user_id.lang or self.env.user.lang or "en_US"

        def _translate(source, /, *args, **kwargs):  # Positional-only: a placeholder may be named "source"
            """Translate a source string and interpolate its arguments.

            Args:
                source: Source string, possibly with ``%`` placeholders.
                *args: Positional placeholders values.
                **kwargs: Named placeholders values.

            Returns:
                str: The translated and formatted string.
            """
            translation = get_translation(module, lang, source, ())
            if args or kwargs:
                try:
                    return translation % (args or kwargs)
                except (TypeError, ValueError, KeyError):
                    bad_translation = translation
                    translation = source % (args or kwargs)
                    _logger.exception(
                        "Bad translation %r for string %r",
                        bad_translation,
                        source,
                    )
            return translation

        return _translate

    def _do_scenario_save(self, message, transition_type, scenario_id=None, step_id=None):
        """Move the terminal to the next step and execute it.

        Handles starting a scenario from its name, following the first transition whose condition is true,
        and the "back" and "restart" requests through the step history. The step code can set ``act``,
        ``res`` and ``val`` to define the answer.

        Args:
            message: Text typed or scanned on the terminal.
            transition_type: "keyboard", "scanner", "back", "restart" or "none".
            scenario_id: Id of the running scenario.
            step_id: Id of the current step.

        Returns:
            tuple: (action code, message lines, value) returned by the executed step.
        """
        self.ensure_one()
        scanner_scenario_obj = self.env["scanner.scenario"]
        scanner_step_obj = self.env["scanner.scenario.step"]
        terminal = self

        tracer = ""

        if transition_type == "restart" or transition_type == "back" and terminal.scenario_id.id:
            if terminal.step_id.no_back:
                step_id = terminal.step_id.id
            else:
                last_call = terminal.step_history_ids[-1]

                # Retrieve last values
                step_id = last_call.step_id.id
                transition = last_call.transition_id
                tracer = last_call.transition_id.tracer
                message = safe_eval(last_call.message)

                # Prevent looping on the same step
                if transition.to_id == terminal.step_id and transition_type == "back":
                    # Remove the history line
                    last_call.unlink()
                    return self._do_scenario_save(
                        message,
                        transition_type,
                        scenario_id=scenario_id,
                        step_id=step_id,
                    )

        # No scenario in arguments, start a new one
        if not self.scenario_id.id:
            # Retrieve the terminal's warehouse
            terminal_warehouse_ids = terminal.warehouse_id.ids
            # Retrieve the warehouse's scenarios
            scenario_ids = scanner_scenario_obj.search([
                ("name", "=", message),
                ("type", "=", "scenario"),
                "|",
                ("warehouse_ids", "=", False),
                ("warehouse_ids", "in", terminal_warehouse_ids),
            ])

            # If at least one scenario was found, pick the start step of the
            # first
            if scenario_ids:
                scenario_id = scenario_ids[0].id
                step_ids = scanner_step_obj.search([
                    ("scenario_id", "=", scenario_id),
                    ("step_start", "=", True),
                ])

                # No start step found on the scenario, return an error
                if not step_ids:
                    return self._send_error([
                        self.env._("No start step found on the scenario"),
                    ])

                step_id = step_ids[0].id
                # Store the first step in terminal history
                terminal.step_history_ids.create({
                    "hardware_id": terminal.id,
                    "step_id": step_id,
                    "message": repr(message),
                })

            else:
                return self._send_error([self.env._("Scenario not found")])

        elif transition_type not in ("back", "none", "restart"):
            # Retrieve outgoing transitions from the current step
            transition_obj = self.env["scanner.scenario.transition"]
            transitions = transition_obj.search([("from_id", "=", step_id)])

            # Evaluate the condition for each transition
            for transition in transitions:
                step_id = False
                ctx = {
                    "context": self.env.context,
                    "model": self.env[transition.from_id.scenario_id.model_id.sudo().model],
                    "cr": self.env.cr,
                    "env": self.env,
                    "uid": self.env.uid,
                    "m": message,
                    "message": message,
                    "t": self,
                    "terminal": self,
                }
                try:
                    expr = safe_eval(str(transition.condition), ctx)
                except Exception:
                    _logger.exception(
                        "Error when evaluating transition condition\n%s",
                        transition.condition,
                    )
                    raise

                # Invalid condition, evaluate next transition
                if not expr:
                    continue

                # Condition passed, go to this step
                step_id = transition.to_id.id
                tracer = transition.tracer

                # Store the old step id if we are on a back step
                if transition.to_id.step_back and (
                    not terminal.step_history_ids or terminal.step_history_ids[-1].transition_id != transition
                ):
                    terminal.step_history_ids.create({
                        "hardware_id": terminal.id,
                        "step_id": transition.to_id.id,
                        "transition_id": transition.id,
                        "message": repr(message),
                    })

                # Valid transition found, stop searching
                break

            # No step found, return an error
            if not step_id:
                terminal.log("No valid transition found !")
                return self._unknown_action([
                    self.env._("Please contact"),
                    self.env._("your"),
                    self.env._("administrator"),
                ])

        # Memorize the current step
        terminal._memorize(scenario_id, step_id)

        # Execute the step
        step = terminal.step_id
        step_translate = terminal._build_step_translator(step)

        ld = {
            "cr": self.env.cr,
            "uid": self.env.uid,
            "env": self.env,
            "model": self.env[step.scenario_id.model_id.sudo().model],
            "term": self,
            "context": self.env.context,
            "m": message,
            "message": message,
            "t": terminal,
            "terminal": terminal,
            "tracer": tracer,
            "scenario": terminal.scenario_id,
            "_": step_translate,
        }

        terminal.log(f"Executing step {step_id} : {step.name}")
        terminal.log(f"Message : {message!r}")
        if tracer:
            terminal.log(f"Tracer : {tracer!r}")

        exec(step.python_code, ld)
        if step.step_stop:
            terminal.empty_scanner_values()

        return (
            ld.get("act", "M"),
            ld.get("res", ["nothing"]),
            ld.get("val", 0),
        )

    def _scenario_save(self, message, transition_type, scenario_id=None, step_id=None):
        """Run ``_do_scenario_save`` in a savepoint and turn failures into terminal answers.

        The savepoint discards the changes of a failing step. Serialization and lock errors are retried with a
        random exponential back-off, user errors are shown with the "back" requirement, other errors are hidden
        from the terminal and reset it. An "A" (automatic) answer immediately triggers the next action.

        Args:
            message: Text typed or scanned on the terminal.
            transition_type: "keyboard", "scanner", "back", "restart" or "none".
            scenario_id: Id of the running scenario.
            step_id: Id of the current step.

        Returns:
            tuple: (action code, message lines, value) to display on the terminal.
        """
        self.ensure_one()
        result = ("M", ["TEST"], False)
        tries = 0
        while True:
            try:
                with self.env.cr.savepoint():
                    result = self._do_scenario_save(
                        message,
                        transition_type,
                        scenario_id=scenario_id,
                        step_id=step_id,
                    )
                break
            except OperationalError as e:
                # Automatically retry the typical transaction serialization
                # errors
                self.env.cr.rollback()
                if e.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                    _logger.warning("[%s] OperationalError", self.code, exc_info=True)
                    result = ("R", ["Please contact", "your", "administrator"], 0)
                    break
                if tries >= MAX_TRIES_ON_CONCURRENCY_FAILURE:
                    _logger.warning(
                        "[%s] Concurrent transaction - OperationalError %s, maximum number of tries reached",
                        self.code,
                        e.pgcode,
                    )
                    result = (
                        "E",
                        [
                            self.env._(
                                "Concurrent transaction - OperationalError %s, maximum number of tries reached",
                                e.pgcode,
                            ),
                        ],
                        True,
                    )
                    break
                wait_time = random.uniform(0.0, 2**tries)
                tries += 1
                _logger.info(
                    "[%s] Concurrent transaction detected (%s), retrying %d/%d in %.04f sec...",
                    self.code,
                    e.pgcode,
                    tries,
                    MAX_TRIES_ON_CONCURRENCY_FAILURE,
                    wait_time,
                )
                time.sleep(wait_time)
            except exceptions.UserError as e:
                # ORM exception, display the error message and require the "go
                # back" action. The savepoint has already discarded the step.
                _logger.warning("[%s] OSV Exception:", self.code, exc_info=True)
                result = ("E", ["error:", str(e), "", ""], True)
                break
            except Exception:
                # Never expose the technical error to the terminal
                _logger.exception("[%s] Exception: ", self.code)
                result = ("R", ["Please contact", "your", "administrator"], 0)
                self.empty_scanner_values()
                break
        self.log(f"Return value : {result!r}")

        # Manage automatic steps
        if result[0] == "A":
            return self.scanner_call(self.code, "action", message=result[2])

        return result

    @api.model
    def _scenario_list(self, parent_id=False):
        """List the names of the scenarios and menus available for this terminal's warehouse.

        Only entries that are usable are returned, meaning menus with children and scenarios with steps.

        Args:
            parent_id: Id of the parent menu, False for the root level.

        Returns:
            list: Scenario names.
        """
        scanner_scenario_obj = self.env["scanner.scenario"]
        scanner_scenario_ids = scanner_scenario_obj.search([
            "|",
            ("warehouse_ids", "=", False),
            ("warehouse_ids", "in", [self.warehouse_id.id]),
            ("parent_id", "=", parent_id),
            "|",
            ("child_ids", "!=", False),
            ("step_ids", "!=", False),
        ])

        return scanner_scenario_ids.mapped("name")

    def _screen_size(self):
        """Return the screen size of the terminal.

        Returns:
            tuple: (width, height) in characters.
        """
        self.ensure_one()
        return (self.screen_width, self.screen_height)

    def log(self, log_message):
        """Log a message when logging is enabled on this terminal.

        Args:
            log_message: Message to log.
        """
        if self.log_enabled:
            _logger.info(f"[{self.code}] {log_message}")
