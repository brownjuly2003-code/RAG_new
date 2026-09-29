"""An escalation handoff is readable in the Evidence tab."""

from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def test_escalation_handoff_is_visible_without_rendering_markup():
    root = Path(__file__).resolve().parents[2]
    summary = '<img src=x onerror="window.injected=true">'
    evidence = {
        "trace_id": "escalation-ui",
        "journeys": [{
            "journey": "shipment-status",
            "outcome": "journey_recorded",
            "terminal_state": "escalated",
            "contract": {"contract_id": "aircargo.shipment-status", "version": "0.1.0"},
            "escalation_brief": {
                "case_id": "case-123",
                "contract_version": "aircargo.shipment-status@0.1.0#digest",
                "reason_codes": ["EVIDENCE_STALE"],
                "evidence_summary": [summary],
            },
        }],
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
                route.fulfill(json={"traces": [{"trace_id": "escalation-ui"}]})
            else:
                route.fulfill(json={})

        page.route("http://rag.test/**", respond)
        page.goto("http://rag.test/")
        page.locator("#btn-load-traces").click()
        page.get_by_role("button", name="Details", exact=True).click()
        page.get_by_role("button", name="Evidence", exact=True).click()
        handoff = page.get_by_role("heading", name="Escalation handoff")
        expect(handoff).to_be_visible()
        expect(page.get_by_text("case-123", exact=True)).to_be_visible()
        expect(page.get_by_text(summary, exact=True)).to_be_visible()
        assert page.locator("#trace-evidence img").count() == 0
        assert page.evaluate("window.injected === undefined")
        browser.close()
