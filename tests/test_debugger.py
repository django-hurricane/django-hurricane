import sys

import mock

from hurricane.server.debugging import setup_debugging, setup_debugpy, setup_pycharm
from hurricane.server.exceptions import IncompatibleOptions
from hurricane.testing import HurricanServerTest


class HurricanDebuggerServerTest(HurricanServerTest):

    alive_route = "/alive"

    @HurricanServerTest.cycle_server(args=["--debugger"])
    def test_debugger(self):
        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 200)
        self.assertIn("Listening for debug clients at port 5678", out)

    def test_incompatible_debugger_and_autoreload(self):
        with self.assertRaises(IncompatibleOptions):
            setup_debugging({"autoreload": True, "debugger": True, "pycharm_host": True})

    def test_debugger_success_and_import_error(self):
        options = {"debugger": True, "debugger_port": 8071}
        with mock.patch("debugpy.listen") as dbgpy:
            dbgpy.side_effect = None
            setup_debugpy(options)
        sys.modules["debugpy"] = None
        options = {"debugger": True}
        setup_debugpy(options)

    def test_pycharm_success_and_import_error(self):
        options = {"pycharm_host": "test", "pycharm_port": 8071}
        with mock.patch("pydevd_pycharm.settrace") as pdvd:
            pdvd.side_effect = None
            setup_pycharm(options)
        sys.modules["pydevd_pycharm"] = None
        options = {"pycharm_host": "test"}
        setup_pycharm(options)
