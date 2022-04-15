from hurricane.testing import HurricanServerTest


class HurricanDebuggerServerTest(HurricanServerTest):

    alive_route = "/alive"

    @HurricanServerTest.cycle_server(args=["--debugger"])
    def test_debugger(self):
        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 200)
        self.assertIn("Listening for debug clients at port 5678", out)

    def test_debugger_import_debugpy(self):
        import sys

        from hurricane.server.debugging import setup_debugpy

        sys.modules["debugpy"] = None
        options = {"debugger": True}
        setup_debugpy(options)

    def test_pycharm_import_pydevd_pycharm(self):
        import sys

        from hurricane.server.debugging import setup_pycharm

        sys.modules["pydevd_pycharm"] = None
        options = {"pycharm_host": True}
        setup_pycharm(options)
