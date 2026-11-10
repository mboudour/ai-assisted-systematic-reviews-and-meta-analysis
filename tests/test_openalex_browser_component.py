"""Tests run offline: python -m unittest discover -s tests -p 'test_openalex_browser_component.py'.

Playwright tests skip when Playwright or Chromium is unavailable. They serve a
minimal local Streamlit-protocol host and intercept every OpenAlex request.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import browser_openalex as module

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "openalex_browser_component"
SECRET = "local_api_key+never-transmit"
EMAIL = "participant-private@example.invalid"


def config(**overrides):
    base = dict(query='("health & care" OR AI) NOT children', per_page=2, max_pages=2,
                year_from=2020, year_to=2024, publication_types=["article", "review"],
                search_scope="title_abstract_exact", require_abstract=True,
                config_id="a" * 64, config_revision=0)
    base.update(overrides)
    return base


def sample_value(settings, *, request_id="a" * 32):
    filters = module._filters(settings)
    return {"records": [{"id": "https://openalex.org/W1", "title": "Test"}], "metadata": {
        "request_id": request_id, "config_id": settings["config_id"],
        "config_revision": settings["config_revision"], "query": settings["query"],
        "endpoint": "https://api.openalex.org/works",
        "search_param": "search" if settings["search_scope"] == "broad" else "search.title_and_abstract.exact",
        "scope": settings["search_scope"], "filters": filters, "filter": ",".join(filters),
        "returned_total": 1, "total_matches": 1, "pages": 1, "pages_fetched": 1,
        "returned": 1, "records_retrieved": 1, "per_page": settings["per_page"],
        "max_pages": settings["max_pages"], "fetched_at_utc": "2026-01-01T00:00:00.000Z",
        "possibly_truncated": False,
    }}


class WrapperTests(unittest.TestCase):
    def test_validation_and_stale_results_even_after_reverting(self):
        state = {}
        last_value = None
        calls = []

        def fake_component(**kwargs):
            nonlocal last_value
            calls.append(kwargs)
            return last_value

        with patch.object(module.st, "session_state", state), patch.object(module, "_component", fake_component):
            self.assertIsNone(module.render_browser_openalex("query A", key="my-widget"))
            settings_a = calls[-1]
            last_value = sample_value(settings_a)
            first = module.render_browser_openalex("query A", key="my-widget")
            self.assertIsNotNone(first)
            self.assertEqual(first[1]["request_id"], "a" * 32)
            self.assertIsNone(module.render_browser_openalex("query B", key="my-widget"))
            self.assertIsNone(module.render_browser_openalex("query A", key="my-widget"))
            self.assertEqual([c["config_revision"] for c in calls], [0, 0, 1, 2])
            self.assertEqual(settings_a["config_id"], calls[-1]["config_id"])
            for args in calls:
                self.assertNotIn("api_key", args)
                self.assertNotIn("email", args)
            for kw in ({"per_page": 0}, {"per_page": 101}, {"max_pages": 6},
                       {"max_pages": True}, {"year_from": 2025, "year_to": 2024},
                       {"publication_types": ["evil"]}, {"search_scope": "invalid"},
                       {"require_abstract": 1}):
                with self.subTest(kw=kw), self.assertRaises(ValueError):
                    module.render_browser_openalex("query", key="x", **kw)

    def test_untrusted_payload_projection_and_malformed_rejection(self):
        settings = config()
        value = sample_value(settings)
        value["records"][0].update({"api_key": "unwanted", "authorships": [{"author": {
            "display_name": "A", "authorization": "unwanted"}}]})
        value["metadata"]["authorization"] = "unwanted"
        records, metadata = module._unpack(value, settings, settings["config_id"], 0)
        self.assertNotIn("unwanted", json.dumps([records, metadata]))
        bad = copy.deepcopy(value)
        bad["metadata"]["query"] = "wrong"
        self.assertIsNone(module._unpack(bad, settings, settings["config_id"], 0))
        bad = copy.deepcopy(value)
        bad["metadata"]["records_retrieved"] = 9000
        self.assertIsNone(module._unpack(bad, settings, settings["config_id"], 0))
        bad = copy.deepcopy(value)
        bad["records"][0]["title"] = {"token": "not text"}
        self.assertIsNone(module._unpack(bad, settings, settings["config_id"], 0))


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


@unittest.skipIf(sync_playwright is None, "Playwright unavailable")
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        chrome = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        try:
            cls.browser = cls.playwright.chromium.launch(
                executable_path=chrome, headless=True, args=["--no-sandbox"])
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest("Chromium unavailable") from exc
        cls.temp = tempfile.TemporaryDirectory()
        temp = Path(cls.temp.name)
        shutil.copytree(ASSETS, temp / "component")
        (temp / "index.html").write_text('''<!doctype html><html><body>
<iframe id="component" src="/component/index.html"></iframe>
<script>
window.messages = []; window.args = %s;
window.renderComponent = function(args) { window.args = args;
 document.getElementById('component').contentWindow.postMessage({type:'streamlit:render',args}, '*'); };
window.addEventListener('message', function(e) {
 if (e.source !== document.getElementById('component').contentWindow) return;
 window.messages.push(e.data);
 if(e.data.type === 'streamlit:componentReady') window.renderComponent(window.args);
});
</script></body></html>''' % json.dumps(config()), encoding="utf-8")
        handler = lambda *a, **kw: QuietHandler(*a, directory=str(temp), **kw)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.browser.close()
        cls.playwright.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.requests = []
        self.console = []
        self.page.on("console", lambda event: self.console.append(event.text))
        self.page.on("pageerror", lambda error: self.console.append(str(error)))
        self.responses = []

        def route_request(route):
            request = route.request
            self.requests.append({"url": request.url, "method": request.method,
                                  "headers": request.headers, "post_data": request.post_data})
            if urlparse(request.url).hostname == "api.openalex.org":
                if request.method == "OPTIONS":
                    route.fulfill(status=204, headers={"access-control-allow-origin": "*",
                        "access-control-allow-headers": "authorization", "access-control-allow-methods": "GET, OPTIONS"})
                    return
                response = self.responses.pop(0) if self.responses else (500, {})
                headers = {"access-control-allow-origin": "*"}
                if len(response) > 2:
                    headers.update(response[2])
                route.fulfill(status=response[0], content_type="application/json",
                              headers=headers, body=json.dumps(response[1]))
            else:
                route.continue_()
        self.page.route("**/*", route_request)
        self.page.goto(self.base, wait_until="load")
        self.frame = self.page.frame_locator("#component")
        self.frame.locator("#credentials").wait_for()
        self.page.wait_for_function("window.messages.some(m => m.type === 'streamlit:componentReady')")

    def tearDown(self):
        self.context.close()

    def choose(self, key=SECRET, email=EMAIL):
        self.frame.locator("#credentials").set_input_files({"name": "credentials.json", "mimeType": "application/json",
            "buffer": json.dumps({"api_key": key, "email": email}).encode()})

    def values(self):
        return self.page.evaluate("window.messages.filter(m => m.type === 'streamlit:setComponentValue')")

    def api_requests(self):
        return [r for r in self.requests if urlparse(r["url"]).hostname == "api.openalex.org" and r["method"] == "GET"]

    def wait_status(self, phrase):
        self.frame.get_by_role("status").get_by_text(phrase, exact=False).wait_for(timeout=5000)

    def assert_no_leaks(self):
        messages = json.dumps(self.page.evaluate("window.messages"))
        html = self.frame.locator("body").inner_text()
        public = json.dumps([messages, html, self.console,
                             [{k: v for k, v in r.items() if k != "headers"} for r in self.requests]])
        for private in (SECRET, EMAIL):
            self.assertNotIn(private, public)
        # The only request header containing the key is the OpenAlex GET.
        for r in self.requests:
            h = json.dumps(r["headers"])
            if SECRET in h:
                self.assertEqual(urlparse(r["url"]).hostname, "api.openalex.org")
                self.assertEqual(r["headers"].get("authorization"), "Bearer " + SECRET)
            self.assertNotIn(EMAIL, h)

    def test_explicit_two_page_search_filters_and_safe_protocol(self):
        self.responses = [
            (200, {"meta": {"count": 3, "next_cursor": "next+/?=&"}, "results": [{
                "id": "https://openalex.org/W1", "title": "First", "publication_year": 2021,
                "authorships": [{"author": {"display_name": "A", "api_key": SECRET}, "extra": SECRET}],
                "primary_location": {"source": {"display_name": "Venue", "authorization": SECRET}},
                "abstract_inverted_index": {"first": [0], "abstract": [1]},
                "concepts": [{"display_name": "C", "private": EMAIL}], "referenced_works": ["https://openalex.org/W9"],
                "api_key": SECRET, "email": EMAIL, "authorization": "Bearer " + SECRET}]}),
            (200, {"meta": {"count": 3, "next_cursor": "another"}, "results": [{"id": "https://openalex.org/W2", "title": "Second"}]}),
        ]
        self.choose()
        self.page.wait_for_timeout(200)
        self.assertEqual(self.api_requests(), [])
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("Search complete")
        messages = self.values()
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0]["isStreamlitMessage"])
        result = messages[0]["value"]
        self.assertEqual([r["title"] for r in result["records"]], ["First", "Second"])
        self.assertEqual(result["records"][0]["authorships"], [{"author": {"display_name": "A"}}])
        meta = result["metadata"]
        self.assertEqual(meta["query"], config()["query"])
        self.assertEqual(meta["endpoint"], "https://api.openalex.org/works")
        self.assertEqual(meta["search_param"], "search.title_and_abstract.exact")
        self.assertEqual(meta["pages_fetched"], 2)
        self.assertEqual(meta["total_matches"], 3)
        self.assertEqual(meta["records_retrieved"], 2)
        self.assertEqual(meta["returned"], 2)
        self.assertTrue(meta["possibly_truncated"])
        self.assertRegex(meta["request_id"], r"^[a-f0-9]{32}$")
        self.assertEqual(meta["filters"], ["from_publication_date:2020-01-01", "to_publication_date:2024-12-31", "type:article|review", "has_abstract:true"])
        requests = self.api_requests()
        self.assertEqual(len(requests), 2)
        q0, q1 = (parse_qs(urlparse(r["url"]).query) for r in requests)
        self.assertEqual(q0["search.title_and_abstract.exact"], [config()["query"]])
        self.assertEqual(q0["cursor"], ["*"])
        self.assertEqual(q1["cursor"], ["next+/?=&"])
        self.assertTrue(all(r["headers"]["authorization"] == "Bearer " + SECRET for r in requests))
        self.page.evaluate("window.renderComponent(window.args)")
        self.page.wait_for_timeout(150)
        self.assertEqual(len(self.api_requests()), 2)
        self.assertEqual(len(self.values()), 1)
        self.assert_no_leaks()

    def test_repeated_click_has_new_request_id_and_broad_scope(self):
        settings = config(search_scope="broad", max_pages=1, per_page=1,
                          year_from=None, year_to=None, publication_types=[], require_abstract=False)
        self.page.evaluate("args => window.renderComponent(args)", settings)
        self.choose()
        self.responses = [(200, {"meta": {"count": 0, "next_cursor": None}, "results": []})] * 2
        for _ in range(2):
            self.frame.get_by_role("button", name="Run Search").click()
            self.wait_status("Search complete")
        self.page.wait_for_function("window.messages.filter(m => m.type === 'streamlit:setComponentValue').length === 2")
        ids = [v["value"]["metadata"]["request_id"] for v in self.values()]
        self.assertNotEqual(ids[0], ids[1])
        for r in self.api_requests():
            q = parse_qs(urlparse(r["url"]).query)
            self.assertEqual(q["search"], [settings["query"]])
            self.assertNotIn("filter", q)
        self.assert_no_leaks()

    def test_invalid_json_missing_keys_and_http_errors_stay_local(self):
        self.frame.locator("#credentials").set_input_files({"name": "bad.json", "mimeType": "application/json", "buffer": b"{"})
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("not valid JSON")
        self.choose(key="")
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("nonempty api_key")
        self.choose()
        for code, text in [(401, "HTTP 401"), (403, "HTTP 403"), (429, "HTTP 429"), (500, "HTTP 500")]:
            self.responses.append((code, {"error": SECRET, "email": EMAIL}))
            self.frame.get_by_role("button", name="Run Search").click()
            self.wait_status(text)
        self.assertEqual(self.values(), [])
        self.assert_no_leaks()

    def test_credential_in_selected_result_or_query_blocks_delivery_and_request(self):
        self.choose()
        self.responses = [(200, {"meta": {"count": 1, "next_cursor": None},
                                 "results": [{"id": "https://openalex.org/W1", "title": "unexpected " + SECRET}]})]
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("response contains private")
        self.assertEqual(self.values(), [])
        previous = len(self.api_requests())
        self.page.evaluate("args => window.renderComponent(args)", config(query="search " + EMAIL))
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("contain private credentials")
        self.assertEqual(len(self.api_requests()), previous)
        self.assertEqual(self.values(), [])
        self.assert_no_leaks()

    def test_cursor_secret_or_repeat_aborts_without_partial_result(self):
        self.choose()
        for cursor, expected in [(SECRET, "contain private credentials"), ("*", "repeated pagination cursor")]:
            self.responses = [(200, {"meta": {"count": 2, "next_cursor": cursor}, "results": [{"id": "W1"}]})]
            self.frame.get_by_role("button", name="Run Search").click()
            self.wait_status(expected)
            self.assertEqual(self.values(), [])
        self.assert_no_leaks()

    def test_second_page_error_discards_partial_records(self):
        self.choose()
        self.responses = [(200, {"meta": {"count": 3, "next_cursor": "page-2"},
                                  "results": [{"id": "W1"}]}),
                          (429, {"error": SECRET})]
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("HTTP 429")
        self.assertEqual(len(self.api_requests()), 2)
        self.assertEqual(self.values(), [])
        self.assert_no_leaks()

    def test_removal_and_changed_settings_cancel_inflight(self):
        self.choose()
        frame = self.page.frame(url=lambda url: "/component/" in url)
        frame.evaluate('''() => { window.realFetch = window.fetch;
          window.fetch = () => new Promise(resolve => { window.releaseFetch = () => resolve(new Response(
          JSON.stringify({meta:{count:1,next_cursor:null},results:[{id:'W1'}]}),
          {status:200,headers:{'Content-Type':'application/json'}})); }); }''')
        self.frame.get_by_role("button", name="Run Search").click()
        frame.wait_for_function("typeof window.releaseFetch === 'function'")
        self.frame.get_by_role("button", name="Remove file").click()
        frame.evaluate("window.releaseFetch()")
        self.page.wait_for_timeout(100)
        self.assertEqual(self.values(), [])
        self.assertTrue(self.frame.get_by_role("button", name="Run Search").is_disabled())
        self.choose()
        frame.evaluate("window.releaseFetch = undefined")
        self.frame.get_by_role("button", name="Run Search").click()
        frame.wait_for_function("typeof window.releaseFetch === 'function'")
        self.choose(key="different-key-12345")
        frame.evaluate("window.releaseFetch()")
        self.page.wait_for_timeout(100)
        self.assertEqual(self.values(), [])
        self.choose()
        frame.evaluate("window.releaseFetch = undefined")
        self.frame.get_by_role("button", name="Run Search").click()
        frame.wait_for_function("typeof window.releaseFetch === 'function'")
        self.page.evaluate("args => window.renderComponent(args)", config(query="changed", config_revision=1))
        frame.evaluate("window.releaseFetch()")
        self.page.wait_for_timeout(100)
        self.assertEqual(self.values(), [])
        frame.evaluate("window.fetch = window.realFetch")
        self.responses = [(200, {"meta": {"count": 0, "next_cursor": None}, "results": []})]
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("Search complete")
        self.assertEqual(self.values()[0]["value"]["metadata"]["query"], "changed")
        self.assert_no_leaks()

    def test_invalid_or_forged_endpoint_argument_cannot_redirect_requests(self):
        args = config()
        args["endpoint"] = "https://evil.invalid/steal"
        args["base_url"] = args["endpoint"]
        self.page.evaluate("args => window.renderComponent(args)", args)
        self.choose()
        self.responses = [(200, {"meta": {"count": 0, "next_cursor": None}, "results": []})]
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("Search complete")
        self.assertTrue(all(r["url"].startswith("https://api.openalex.org/works?") for r in self.api_requests()))
        args["per_page"] = 1000
        self.page.evaluate("args => window.renderComponent(args)", args)
        self.wait_status("Invalid search settings")
        self.assertTrue(self.frame.get_by_role("button", name="Run Search").is_disabled())
        self.assert_no_leaks()

    def test_redirect_is_rejected_and_never_forwards_the_key(self):
        self.choose()
        self.responses = [(302, {}, {"location": "https://evil.invalid/steal"})]
        self.frame.get_by_role("button", name="Run Search").click()
        self.wait_status("request failed")
        self.assertEqual(self.values(), [])
        self.assertFalse(any(urlparse(r["url"]).hostname == "evil.invalid" for r in self.requests))
        self.assert_no_leaks()


@unittest.skipIf(sync_playwright is None, "Playwright unavailable")
class RealStreamlitTests(unittest.TestCase):
    def test_actual_streamlit_rerun_only_sends_results(self):
        chrome = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "app.py"
            app.write_text(
                "import sys\n"
                f"sys.path.insert(0, {str(ROOT)!r})\n"
                "import streamlit as st\n"
                "from browser_openalex import render_browser_openalex\n"
                "st.title('Browser component integration')\n"
                "query = st.text_input('Query', value='clinical research')\n"
                "value = render_browser_openalex(query, key='live-test', per_page=1, max_pages=1)\n"
                "if value is not None:\n"
                "    st.write('RECEIVED RESULT', value[0][0]['title'], value[1]['request_id'])\n",
                encoding="utf-8",
            )
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            python = os.environ.get("STREAMLIT_TEST_PYTHON", sys.executable)
            process = subprocess.Popen([python, "-m", "streamlit", "run", str(app),
                "--server.address", "127.0.0.1", "--server.port", str(port),
                "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        self.fail("Streamlit exited during startup")
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    self.fail("Streamlit startup timed out")
                with sync_playwright() as p:
                    try:
                        browser = p.chromium.launch(executable_path=chrome, headless=True, args=["--no-sandbox"])
                    except Exception as exc:
                        raise unittest.SkipTest("Chromium unavailable") from exc
                    try:
                        page = browser.new_page()
                        requests = []
                        sent_frames = []
                        page.on("websocket", lambda ws: ws.on("framesent", lambda data: sent_frames.append(data)))

                        def route_request(route):
                            request = route.request
                            requests.append((request.url, request.method, request.headers, request.post_data))
                            if urlparse(request.url).hostname == "api.openalex.org":
                                if request.method == "OPTIONS":
                                    route.fulfill(status=204, headers={"access-control-allow-origin": "*",
                                        "access-control-allow-headers": "authorization", "access-control-allow-methods": "GET, OPTIONS"})
                                else:
                                    route.fulfill(status=200, content_type="application/json",
                                        headers={"access-control-allow-origin": "*"},
                                        body=json.dumps({"meta": {"count": 1, "next_cursor": None},
                                                         "results": [{"id": "W1", "title": "Browser paper"}]}))
                            else:
                                route.continue_()
                        page.route("**/*", route_request)
                        page.goto(f"http://127.0.0.1:{port}")
                        component = page.frame_locator('iframe[title*="openalex_browser_component"]')
                        component.locator("#credentials").set_input_files({"name": "credentials.json",
                            "mimeType": "application/json", "buffer": json.dumps({"api_key": SECRET, "email": EMAIL}).encode()})
                        self.assertFalse(any(urlparse(r[0]).hostname == "api.openalex.org" for r in requests))
                        component.get_by_role("button", name="Run Search").click()
                        page.get_by_text("RECEIVED RESULT", exact=False).wait_for(timeout=15000)
                        self.assertIn("Browser paper", page.locator("body").inner_text())
                        self.assertEqual(sum(urlparse(r[0]).hostname == "api.openalex.org" and r[1] == "GET" for r in requests), 1)
                        for frame in sent_frames:
                            raw = frame.encode() if isinstance(frame, str) else frame
                            self.assertNotIn(SECRET.encode(), raw)
                            self.assertNotIn(EMAIL.encode(), raw)
                        for url, method, headers, body in requests:
                            self.assertNotIn(SECRET, url)
                            self.assertNotIn(EMAIL, url)
                            self.assertNotIn(SECRET, body or "")
                            self.assertNotIn(EMAIL, body or "")
                            if SECRET in json.dumps(headers):
                                self.assertEqual(urlparse(url).hostname, "api.openalex.org")
                                self.assertEqual(headers.get("authorization"), "Bearer " + SECRET)
                        # Rerendering with changed settings suppresses the old value.
                        page.get_by_label("Query").fill("new query")
                        page.get_by_label("Query").press("Enter")
                        page.get_by_text("RECEIVED RESULT", exact=False).wait_for(state="detached", timeout=10000)
                        self.assertEqual(sum(urlparse(r[0]).hostname == "api.openalex.org" and r[1] == "GET" for r in requests), 1)
                    finally:
                        browser.close()
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    unittest.main()
