(function () {
  "use strict";

  var legacyStorageKey = "rag_admin_token";
  var tokenInput = document.getElementById("token");
  var tokenStatus = document.getElementById("token-status");
  var tracesTableBody = document.querySelector("#traces-table tbody");
  var auditTableBody = document.querySelector("#audit-table tbody");

  // Graceful migration: purge any bearer token left in localStorage by an
  // earlier build. Auth now rides on an httpOnly cookie (set via /api/auth/session)
  // that JavaScript cannot read, so the XSS-theft surface is gone.
  try {
    localStorage.removeItem(legacyStorageKey);
  } catch (_) {
    /* localStorage may be unavailable; nothing to migrate. */
  }

  function buildHeaders() {
    // No Authorization header: requests authenticate via the httpOnly cookie,
    // copied into the Authorization header server-side by the cookie bridge.
    return { "Content-Type": "application/json" };
  }

  async function establishSession(token) {
    var response = await fetch("/api/auth/session", {
      method: "POST",
      headers: token ? { Authorization: "Bearer " + token } : {}
    });
    return response.ok;
  }

  async function api(method, path, body) {
    var options = {
      method: method,
      headers: buildHeaders()
    };

    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }

    var response = await fetch(path, options);
    var text = await response.text();
    var parsed = text;

    try {
      parsed = JSON.parse(text);
    } catch (_) {
      parsed = text;
    }

    return {
      ok: response.ok,
      status: response.status,
      body: parsed
    };
  }

  document.getElementById("save-token").addEventListener("click", async function () {
    var token = tokenInput.value.trim();
    if (!token) {
      tokenStatus.textContent = "Enter a bearer token first.";
      return;
    }
    tokenStatus.textContent = "Establishing session...";
    var ok = await establishSession(token);
    if (ok) {
      tokenInput.value = "";
      tokenStatus.textContent = "Session cookie set (httpOnly). Token is no longer stored in the browser.";
    } else {
      tokenStatus.textContent = "Authorization failed. Check the token and try again.";
    }
  });

  document.getElementById("logout").addEventListener("click", async function () {
    tokenStatus.textContent = "Logging out...";
    var response = await fetch("/api/auth/logout", { method: "POST" });
    tokenStatus.textContent = response.ok
      ? "Logged out. Session cookie cleared."
      : "Logout failed (HTTP " + response.status + ").";
  });

  document.querySelectorAll(".tabs button").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".tabs button").forEach(function (item) {
        item.classList.remove("active");
      });
      document.querySelectorAll("main section").forEach(function (section) {
        section.classList.remove("active");
      });
      button.classList.add("active");
      document.getElementById("tab-" + button.dataset.tab).classList.add("active");
      if (button.dataset.tab === "metrics") {
        refreshMetrics();
      }
    });
  });

  document.getElementById("btn-reset").addEventListener("click", async function () {
    var output = document.getElementById("breaker-output");
    var result;

    output.textContent = "Loading...";
    result = await api("POST", "/api/admin/circuit-breaker/reset");
    output.textContent = JSON.stringify({ status: result.status, body: result.body }, null, 2);
  });

  // --- Phase A.3: the Evidence view on a trace ------------------------------
  // The raw JSON pane stays exactly what it was. This one answers the question
  // the raw pane cannot: why the run reached that state, on what evidence, and
  // how old that evidence was when it was read. Everything is built with
  // textContent -- an evidence bundle carries source text, and innerHTML here
  // would make a shipment status an injection point.
  var evidencePane = document.getElementById("trace-evidence");
  var rawPane = document.getElementById("trace-detail");
  var rawViewButton = document.getElementById("btn-trace-raw");
  var evidenceViewButton = document.getElementById("btn-trace-evidence");
  var exportEvidenceButton = document.getElementById("btn-export-evidence");
  var loadedEvidence = null;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function describeAge(seconds) {
    // Age at the moment the shadow recorded the step, not age now: the same
    // trace has to read the same way next week.
    if (seconds === null || seconds === undefined || !isFinite(Number(seconds))) {
      return "age unknown";
    }
    var value = Number(seconds);
    if (value < 90) {
      return Math.round(value) + "s old";
    }
    if (value < 5400) {
      return Math.round(value / 60) + "m old";
    }
    if (value < 172800) {
      return Math.round(value / 3600) + "h old";
    }
    return Math.round(value / 86400) + "d old";
  }

  function definitionList(pairs) {
    var list = document.createElement("dl");
    pairs.forEach(function (pair) {
      if (pair[1] === null || pair[1] === undefined || pair[1] === "") {
        return;
      }
      list.appendChild(el("dt", null, pair[0]));
      list.appendChild(el("dd", null, pair[1]));
    });
    return list;
  }

  function renderSource(source) {
    var line = el("p", "source");
    line.appendChild(document.createTextNode(source.kind + ": " + (source.label || "-") + " - "));
    line.appendChild(el("span", "digest", String(source.digest || "").slice(0, 12)));
    line.appendChild(document.createTextNode(
      " - " + describeAge(source.age_seconds) + " - observed " + (source.observed_at || "at an unknown time")
    ));
    if (source.digest_matches === false) {
      // The claim cites one digest and the evidence carries another. Worth
      // seeing: it means the claim was written against evidence that moved.
      line.appendChild(document.createTextNode(" - cites a different digest"));
    }
    return line;
  }

  function renderJourney(journey) {
    var contract = journey.contract || {};
    var receipt = journey.replay_receipt || {};
    var box = document.createElement("div");

    if (journey.outcome === "journey_declined" || journey.outcome === "producer_failure") {
      box.appendChild(el("h3", null, "Outcome"));
      var minimalOutcome = el("p");
      minimalOutcome.appendChild(el("span", "terminal", journey.terminal_state || journey.outcome));
      if (journey.reason_codes && journey.reason_codes.length) {
        minimalOutcome.appendChild(document.createTextNode(" " + journey.reason_codes.join(", ")));
      }
      box.appendChild(minimalOutcome);
      box.appendChild(el(
        "p",
        "empty",
        journey.outcome === "journey_declined"
          ? "This request did not enter the journey; no source or policy was called."
          : "The resolution producer failed before it could record evidence."
      ));
      return box;
    }

    box.appendChild(el("h3", null, "Contract"));
    box.appendChild(definitionList([
      ["journey", journey.journey],
      ["contract", contract.contract_id],
      ["version", contract.version],
      ["digest", contract.digest]
    ]));

    box.appendChild(el("h3", null, "Outcome"));
    var outcome = el("p");
    outcome.appendChild(el("span", "terminal", journey.terminal_state || "-"));
    if (journey.reason_codes && journey.reason_codes.length) {
      outcome.appendChild(document.createTextNode(" " + journey.reason_codes.join(", ")));
    }
    box.appendChild(outcome);

    box.appendChild(el("h3", null, "Policy decision"));
    if (journey.policy) {
      var policyDetail = journey.policy.detail || {};
      box.appendChild(definitionList([
        ["decision", policyDetail.decision],
        ["authority", journey.policy.source_id],
        ["data revision", journey.policy.source_version],
        ["implementation", policyDetail.implementation_version],
        ["recorded at", journey.policy.observed_at],
        ["valid from", policyDetail.valid_from],
        ["valid to", policyDetail.valid_to || "open"],
        ["freshness", describeAge(journey.policy.age_seconds)]
      ]));
    } else {
      box.appendChild(el("p", "empty", "No policy evidence in this bundle."));
    }

    box.appendChild(el("h3", null, "Claims and the evidence behind them"));
    var claims = journey.claims || [];
    if (!claims.length) {
      box.appendChild(el("p", "empty", "This run made no material claims."));
    }
    claims.forEach(function (claim) {
      var claimBox = el("div", "claim");
      claimBox.appendChild(el("p", "claim-text", claim.text || claim.claim_id || "-"));
      (claim.sources || []).forEach(function (source) {
        claimBox.appendChild(renderSource(source));
      });
      if (claim.unresolved && claim.unresolved.length) {
        claimBox.appendChild(el(
          "p",
          "source",
          "cites evidence this bundle does not carry: " + claim.unresolved.join(", ")
        ));
      }
      box.appendChild(claimBox);
    });

    box.appendChild(el("h3", null, "Postconditions"));
    var postconditions = journey.postconditions || [];
    if (!postconditions.length) {
      box.appendChild(el("p", "empty", "No postconditions were checked."));
    }
    postconditions.forEach(function (postcondition) {
      box.appendChild(el(
        "p",
        "source",
        postcondition.postcondition_id + " " + postcondition.version + " - " + postcondition.result
      ));
    });

    box.appendChild(el("h3", null, "Replay receipt"));
    box.appendChild(definitionList([
      ["mode", receipt.mode],
      ["case", receipt.case_id],
      ["case version", receipt.case_version],
      ["correlation", receipt.correlation_id],
      ["contract digest", receipt.contract_digest],
      ["source", receipt.source_id],
      ["source version", receipt.source_version],
      ["source digest", receipt.source_digest],
      ["policy authority", receipt.policy_authority],
      ["policy revision", receipt.policy_data_revision],
      ["policy digest", receipt.policy_digest],
      ["evidence as of", journey.as_of]
    ]));

    return box;
  }

  function setEvidence(view) {
    loadedEvidence = view;
    evidencePane.textContent = "";
    var journeys = view && Array.isArray(view.journeys) ? view.journeys : [];
    var retrievalPaths = view && Array.isArray(view.retrieval_paths) ? view.retrieval_paths : [];
    exportEvidenceButton.disabled = journeys.length === 0 && retrievalPaths.length === 0;

    if (!view) {
      evidencePane.appendChild(el("p", "empty", "Evidence could not be loaded for this trace."));
      return;
    }
    retrievalPaths.forEach(function (retrieval) {
      var path = retrieval.path || {};
      evidencePane.appendChild(el("h3", null, "Structural retrieval path"));
      evidencePane.appendChild(definitionList([
        ["strategy", retrieval.strategy],
        ["category prefilter", path.prefilter_applied ? "applied" : "not applied"],
        ["sections", (path.sections || []).join(", ") || "none"],
        ["retrieved contexts", path.retrieved_contexts],
        ["retained contexts", path.retained_contexts],
        ["expanded contexts", path.expanded_contexts]
      ]));
      evidencePane.appendChild(el("p", "source", "Structural retrieval only; no entity traversal."));
    });
    if (!journeys.length) {
      evidencePane.appendChild(el(
        "p",
        "empty",
        "Resolution shadow was disabled for this trace."
      ));
      return;
    }
    journeys.forEach(function (journey) {
      evidencePane.appendChild(renderJourney(journey));
    });
  }

  function showTraceView(name) {
    var showEvidence = name === "evidence";
    evidencePane.hidden = !showEvidence;
    rawPane.hidden = showEvidence;
    rawViewButton.classList.toggle("selected", !showEvidence);
    evidenceViewButton.classList.toggle("selected", showEvidence);
    rawViewButton.setAttribute("aria-pressed", String(!showEvidence));
    evidenceViewButton.setAttribute("aria-pressed", String(showEvidence));
  }

  rawViewButton.addEventListener("click", function () {
    showTraceView("raw");
  });

  evidenceViewButton.addEventListener("click", function () {
    showTraceView("evidence");
  });

  exportEvidenceButton.addEventListener("click", function () {
    if (!loadedEvidence) {
      return;
    }
    var blob = new Blob([JSON.stringify(loadedEvidence, null, 2)], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "evidence-" + (loadedEvidence.trace_id || "trace") + ".json";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  });

  document.getElementById("btn-load-traces").addEventListener("click", async function () {
    var limit = document.getElementById("traces-limit").value;
    var output = document.getElementById("traces-output");
    var detail = document.getElementById("trace-detail");
    var result = await api("GET", "/api/admin/traces?limit=" + encodeURIComponent(limit));

    tracesTableBody.innerHTML = "";
    detail.textContent = "";
    setEvidence(null);

    if (!result.ok || !result.body || !Array.isArray(result.body.traces)) {
      output.textContent = JSON.stringify({ status: result.status, body: result.body }, null, 2);
      return;
    }

    output.textContent = JSON.stringify({ status: result.status, count: result.body.traces.length }, null, 2);

    result.body.traces.forEach(function (trace) {
      var row = document.createElement("tr");
      var traceIdCell = document.createElement("td");
      var startedCell = document.createElement("td");
      var finishedCell = document.createElement("td");
      var actionCell = document.createElement("td");
      var detailsButton = document.createElement("button");

      traceIdCell.textContent = trace.trace_id || "";
      startedCell.textContent = trace.started_at || "";
      finishedCell.textContent = trace.finished_at || "";

      detailsButton.type = "button";
      detailsButton.textContent = "Details";
      detailsButton.addEventListener("click", async function () {
        var traceId = trace.trace_id || "";
        var detailResult = await api("GET", "/api/admin/traces/" + encodeURIComponent(traceId));
        detail.textContent = JSON.stringify({ status: detailResult.status, body: detailResult.body }, null, 2);

        var evidenceResult = await api(
          "GET",
          "/api/admin/traces/" + encodeURIComponent(traceId) + "/evidence"
        );
        setEvidence(evidenceResult.ok ? evidenceResult.body : null);
      });

      actionCell.appendChild(detailsButton);
      row.appendChild(traceIdCell);
      row.appendChild(startedCell);
      row.appendChild(finishedCell);
      row.appendChild(actionCell);
      tracesTableBody.appendChild(row);
    });
  });

  document.getElementById("btn-purge-traces").addEventListener("click", async function () {
    var days = document.getElementById("traces-purge-days").value;
    var output = document.getElementById("traces-output");
    var result = await api("DELETE", "/api/admin/traces?older_than_days=" + encodeURIComponent(days));

    output.textContent = JSON.stringify({ status: result.status, body: result.body }, null, 2);
    if (result.ok) {
      document.getElementById("btn-load-traces").click();
    }
  });

  document.getElementById("btn-load-audit").addEventListener("click", async function () {
    var params = new URLSearchParams();
    var actor = document.getElementById("audit-actor").value;
    var action = document.getElementById("audit-action").value;
    var limit = document.getElementById("audit-limit").value;
    var output = document.getElementById("audit-output");
    var result;

    params.set("limit", limit);
    if (actor) {
      params.set("actor", actor);
    }
    if (action) {
      params.set("action", action);
    }

    result = await api("GET", "/api/admin/audit?" + params.toString());
    auditTableBody.innerHTML = "";

    if (!result.ok || !result.body || !Array.isArray(result.body.entries)) {
      output.textContent = JSON.stringify({ status: result.status, body: result.body }, null, 2);
      return;
    }

    output.textContent = JSON.stringify({ status: result.status, count: result.body.entries.length }, null, 2);

    result.body.entries.forEach(function (entry) {
      var row = document.createElement("tr");
      var tsCell = document.createElement("td");
      var actorCell = document.createElement("td");
      var actionCell = document.createElement("td");
      var resourceCell = document.createElement("td");
      var ipCell = document.createElement("td");

      tsCell.textContent = entry.ts || "";
      actorCell.textContent = entry.actor || "";
      actionCell.textContent = entry.action || "";
      resourceCell.textContent = entry.resource || "";
      ipCell.textContent = entry.ip_address || "";

      row.appendChild(tsCell);
      row.appendChild(actorCell);
      row.appendChild(actionCell);
      row.appendChild(resourceCell);
      row.appendChild(ipCell);
      auditTableBody.appendChild(row);
    });
  });

  document.getElementById("btn-purge-audit").addEventListener("click", async function () {
    var days = document.getElementById("audit-purge-days").value;
    var output = document.getElementById("audit-output");
    var result = await api("DELETE", "/api/admin/audit-log?older_than_days=" + encodeURIComponent(days));

    output.textContent = JSON.stringify({ status: result.status, body: result.body }, null, 2);
    if (result.ok) {
      document.getElementById("btn-load-audit").click();
    }
  });

  async function refreshMetrics() {
    var output = document.getElementById("metrics-output");
    var result = await api("GET", "/api/metrics");

    output.textContent = JSON.stringify({ status: result.status, body: result.body }, null, 2);
  }

  setInterval(function () {
    if (document.getElementById("tab-metrics").classList.contains("active")) {
      refreshMetrics();
    }
  }, 5000);

  refreshMetrics();
})();
