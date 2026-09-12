"""Browser contract for structural retrieval evidence, including safe text rendering."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def test_structural_path_is_visible_and_exportable_without_resolution(tmp_path):
    root = Path(__file__).resolve().parents[2]
    section = '<img src=x onerror="window.injected=true">'
    evidence = {
        "trace_id": "graph-ui",
        "journeys": [],
        "retrieval_paths": [{"strategy": "graph", "path": {
            "kind": "structural", "prefilter_applied": False,
            "sections": [section], "entities": [], "hops": 0,
            "retrieved_contexts": 2, "retained_contexts": 1, "expanded_contexts": 1,
        }}],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        def respond(route):
            path = route.request.url.split("http://rag.test", 1)[1]
            if path == "/":
                route.fulfill(path=str(root / "static/admin.html"), content_type="text/html")
            elif path == "/static/admin.js":
                route.fulfill(path=str(root / "static/admin.js"), content_type="text/javascript")
            elif path.endswith("/evidence"):
                route.fulfill(json=evidence)
            elif path.startswith("/api/admin/traces?"):
                route.fulfill(json={"traces": [{"trace_id": "graph-ui"}]})
            else:
                route.fulfill(json={})

        page.route("http://rag.test/**", respond)
        page.goto("http://rag.test/")
        page.locator("#btn-load-traces").click()
        page.get_by_role("button", name="Details", exact=True).click()
        page.get_by_role("button", name="Evidence", exact=True).click()
        expect(page.get_by_role("heading", name="Structural retrieval path")).to_be_visible()
        expect(page.get_by_text(section, exact=True)).to_be_visible()
        assert page.locator("#trace-evidence img").count() == 0
        assert page.evaluate("window.injected === undefined")
        export = page.get_by_role("button", name="Export evidence JSON")
        expect(export).to_be_enabled()
        with page.expect_download() as download:
            export.click()
        assert json.loads(Path(download.value.path()).read_text(encoding="utf-8")) == evidence
        evidence.pop("retrieval_paths")
        page.get_by_role("button", name="Details", exact=True).click()
        expect(page.get_by_role("heading", name="Structural retrieval path")).to_have_count(0)
        expect(export).to_be_disabled()
        browser.close()
