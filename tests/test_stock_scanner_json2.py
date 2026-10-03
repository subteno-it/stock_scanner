# Copyright 2026 Subteno (https://www.subteno.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


import inspect
import json

from odoo.exceptions import AccessError
from odoo.models import get_public_method
from odoo.tests import common, tagged


@tagged("post_install", "-at_install", "stock_scanner")
class TestStockScannerJson2(common.TransactionCase):
    """Check that the methods used by odoo-sentinel are callable through JSON-2.

    The ``/json/2/<model>/<method>`` controller only accepts public methods,
    named arguments, and no ``ids`` on ``@api.model`` methods.
    """

    def _check_callable_with(self, method_name, **kwargs):
        """Reproduce the checks done by the JSON-2 controller.

        Args:
            method_name: Name of the ``scanner.hardware`` method.
            **kwargs: Named arguments the client will send.

        Returns:
            The method, once validated.
        """
        model = self.env["scanner.hardware"]
        func = get_public_method(model, method_name)
        self.assertTrue(
            hasattr(func, "_api_model"),
            f"{method_name} must stay an @api.model method (no ids sent by sentinel)",
        )
        inspect.signature(func).bind(model, **kwargs)
        return func

    def test_scanner_call_is_callable(self):
        """scanner_call must accept the named arguments sent by the client."""
        self._check_callable_with(
            "scanner_call",
            terminal_number="hard1",
            action="action",
            message="msg",
            transition_type="keyboard",
        )

    def test_scanner_check_is_callable(self):
        """scanner_check must accept the named argument sent by the client."""
        self._check_callable_with("scanner_check", terminal_number="hard1")

    def test_private_methods_are_not_exposed(self):
        """Private helper methods must stay unreachable through JSON-2."""
        model = self.env["scanner.hardware"]
        for method_name in ("_get_terminal", "_scanner_call", "_scenario_save"):
            with self.assertRaises(AccessError):
                get_public_method(model, method_name)

    def test_scanner_call_result_is_json_serializable(self):
        """The scanner_call result must survive JSON encoding with tuples becoming lists."""
        hardware = self.env.ref("stock_scanner.scanner_hardware_1")
        result = self.env["scanner.hardware"].scanner_call(hardware.code, action="screen_size")
        self.assertEqual(json.loads(json.dumps(result)), ["M", [40, 20], 0])
