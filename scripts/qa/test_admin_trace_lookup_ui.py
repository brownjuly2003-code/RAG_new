"""An operator can open a known trace without finding it in the recent list."""

from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def test_open_trace_by_id_and_direct_link():
    root = Path(__file__).resolve().parents[2]
    trace_id = "123e4567-e89b-42d3-a456-426614174000"
    evidence = {
        "trace_id": trace_id,
        "journeys": [{
            "journey": "shipment-status",
            "terminal_state": "verified",
            "contract": {"contract_id": "aircargo.shipment-status", "version": "0.1.0"},
        }],
    }
    requests = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        def respond(route):
            path = urlsplit(route.request.url).path
            if path == "/":
                route.fulfill(path=str(root / "static/admin.html"), content_type="text/html")
            elif path == "/static/admin.js":
                route.fulfill(path=str(root / "static/admin.js"), content_type="text/javascript")
            elif path == f"/api/admin/traces/{trace_id}":
                requests.append(path)
                route.fulfill(json={"trace_id": trace_id, "steps": []})
            elif path == f"/api/admin/traces/{trace_id}/evidence":
                requests.append(path)
                route.fulfill(json=evidence)
            elif path.startswith("/api/admin/traces?"):
                route.fulfill(json={"traces": []})
            else:
                route.fulfill(json={})

        page.route("http://rag.test/**", respond)
        page.goto("http://rag.test/")
        page.get_by_role("button", name="Traces", exact=True).click()
        page.get_by_label("Trace ID").fill(trace_id)
        page.get_by_role("button", name="Open trace").click()
        expect(page.locator("#trace-evidence")).to_contain_text("shipment-status")
        expect(page.locator("#btn-trace-evidence")).to_have_attribute("aria-pressed", "true")
        assert requests == [
            f"/api/admin/traces/{trace_id}",
            f"/api/admin/traces/{trace_id}/evidence",
        ]

        requests.clear()
        page.goto(f"http://rag.test/?trace_id={trace_id}")
        expect(page.locator("#tab-traces")).to_have_class("active")
        expect(page.locator("#trace-evidence")).to_contain_text("shipment-status")
        assert requests == [
            f"/api/admin/traces/{trace_id}",
            f"/api/admin/traces/{trace_id}/evidence",
        ]
        browser.close()
