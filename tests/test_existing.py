"""Existing regression suite. Release investigation can discover additional cases."""

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from customer_service.server import Handler, MAX_BODY_BYTES, import_customer


class CustomerTests(unittest.TestCase):
    def test_explicit_nickname(self):
        self.assertEqual(
            import_customer({"name": "Avery Chen", "nickname": "Aves"}),
            {"customer": {"name": "Avery Chen", "nickname": "Aves"}},
        )

    def test_explicit_null(self):
        self.assertEqual(
            import_customer({"name": "Avery Chen", "nickname": None}),
            {"customer": {"name": "Avery Chen", "nickname": None}},
        )

    def test_malformed_customer(self):
        for payload in (
            {"name": "Avery Chen", "nickname": {"value": "Aves"}},
            {"nickname": "Aves"},
            {"name": 123, "nickname": None},
            {"name": "", "nickname": None},
            {"name": "Avery Chen", "nickname": 123},
            {"name": "Avery Chen", "nickname": None, "admin": True},
            [], None,
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                import_customer(payload)


class QuietHandler(Handler):
    def log_message(self, *args):
        pass


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, response.read(), response.getheader("Content-Type")
        finally:
            connection.close()

    def test_health(self):
        status, body, _ = self.request("GET", "/health")
        self.assertEqual((status, json.loads(body)), (200, {"status": "ok"}))

    def test_demo_page(self):
        status, body, content_type = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"Customer import", body)

    def test_import(self):
        status, body, _ = self.request(
            "POST", "/customers/import",
            json.dumps({"name": "Avery Chen", "nickname": "Aves"}),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["customer"]["nickname"], "Aves")

    def test_invalid_customer_has_stable_error(self):
        status, body, _ = self.request(
            "POST", "/customers/import", '{"nickname":{}}',
            {"Content-Type": "application/json"},
        )
        self.assertEqual((status, json.loads(body)), (422, {"error": "invalid_customer"}))

    def test_malformed_json(self):
        status, body, _ = self.request(
            "POST", "/customers/import", "{", {"Content-Type": "application/json"},
        )
        self.assertEqual((status, json.loads(body)), (400, {"error": "invalid_json"}))

    def test_oversized_request(self):
        status, body, _ = self.request(
            "POST", "/customers/import", "x" * (MAX_BODY_BYTES + 1),
            {"Content-Type": "application/json"},
        )
        self.assertEqual((status, json.loads(body)), (413, {"error": "request_too_large"}))

    def test_unknown_path(self):
        for method in ("GET", "POST"):
            with self.subTest(method=method):
                status, body, _ = self.request(method, "/missing")
                self.assertEqual((status, json.loads(body)), (404, {"error": "not_found"}))


if __name__ == "__main__":
    unittest.main()
