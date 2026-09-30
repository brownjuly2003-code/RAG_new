(function () {
  "use strict";

  var form = document.getElementById("ask-form");
  var question = document.getElementById("question");
  var button = document.getElementById("ask-button");
  var panel = document.getElementById("response-panel");
  var state = document.getElementById("response-state");
  var answer = document.getElementById("answer");
  var traceId = document.getElementById("trace-id");
  var evidenceLink = document.getElementById("evidence-link");

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    button.disabled = true;
    panel.setAttribute("aria-busy", "true");
    state.textContent = "Запрос выполняется /api/ask";
    answer.textContent = "Продукт обрабатывает вопрос и проверяет источники…";
    answer.classList.add("placeholder");
    traceId.textContent = "—";
    evidenceLink.hidden = true;

    try {
      var response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.value.trim() })
      });
      var data = await response.json();
      if (!response.ok) {
        throw new Error("HTTP " + response.status + ": " + (data.detail || "API error"));
      }
      answer.classList.remove("placeholder");
      answer.textContent = data.answer || "API вернул пустой ответ.";
      state.textContent = "Ответ / маршрут: " + (data.route || "не указан");
      if (data.trace_id) {
        traceId.textContent = data.trace_id;
        evidenceLink.href = "/static/admin.html?trace_id=" + encodeURIComponent(data.trace_id);
        evidenceLink.hidden = false;
      }
    } catch (error) {
      state.textContent = "Запрос не завершён";
      answer.classList.remove("placeholder");
      answer.textContent = error.message || "Ошибка соединения с API.";
    } finally {
      panel.setAttribute("aria-busy", "false");
      button.disabled = false;
    }
  });
}());
