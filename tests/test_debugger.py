from hurricane.testing import HurricanServerTest


class HurricanDebuggerServerTest(HurricanServerTest):

    alive_route = "/alive"

    @HurricanServerTest.cycle_server(args=["--debugger"])
    def test_debugger(self):
        res = self.probe_client.get(self.alive_route)
        out, err = self.driver.get_output(read_all=True)
        self.assertEqual(res.status, 200)
