from hurricane.testing import HurricanServerTest


class HurricaneUploadServerTests(HurricanServerTest):
    @HurricanServerTest.cycle_server
    def test_file_upload_succeeds(self):
        resp = self.app_client.post_file(
            "/upload", "tests/testapp/test_media/testfile.txt"
        )
        self.assertEqual(resp.status, 200)

    @HurricanServerTest.cycle_server(
        args=["--max-body-size", f"{1024}", "--max-buffer-size", f"{1024}"]
    )
    def test_file_upload_fails(self):
        with self.assertRaises(ConnectionResetError):
            resp = self.app_client.post_file(
                "/upload", "tests/testapp/test_media/testfile.txt"
            )
