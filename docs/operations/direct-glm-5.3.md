# Прямой вызов GLM 5.3

Рабочий маршрут проверен 2026-09-21: HTTP POST к Z.ai, модель в ответе
`glm-5.3`. Передаём `output_config.effort=xhigh`. Это прямой API-вызов,
без Grok, OpenCode и Claude CLI. Наличие параметра в запросе не доказывает,
что сервер строго соблюдает бюджет рассуждений.

## Запуск на Windows

Нужен установленный Python 3.10+ и существующий локальный файл
`C:\Users\uedom\.claude-glm\settings.json`. Из его объекта `env` читаются
`ANTHROPIC_BASE_URL` (`https://api.z.ai/api/anthropic`) и
`ANTHROPIC_AUTH_TOKEN`. Не выводить настройки или токен и не добавлять их
в Git. WSL, Docker и установка дополнительных библиотек не нужны.

Сохранить следующий код как `.tmp/glm-direct.py` в рабочем каталоге.
В `.tmp/prompt.txt` записать узкую задачу в UTF-8: контекст, допустимые
файлы, требуемый формат результата и критерии проверки. API не видит
репозиторий и самостоятельно не изменяет файлы: нужный контекст передаётся
в запросе, полученный патч проверяет и применяет ведущий агент.

```python
import json
from pathlib import Path
import sys
import time
import urllib.request

prompt_path, output_path = map(Path, sys.argv[1:3])
settings_path = Path.home() / ".claude-glm" / "settings.json"
env = json.loads(settings_path.read_text(encoding="utf-8"))["env"]
base_url = env["ANTHROPIC_BASE_URL"].rstrip("/")
if base_url != "https://api.z.ai/api/anthropic":
    raise SystemExit("Unexpected API endpoint; inspect configuration locally")
payload = {
    "model": "glm-5.3",
    "max_tokens": 48000,
    "thinking": {"type": "enabled", "budget_tokens": 8000},
    "output_config": {"effort": "xhigh"},
    "stream": True,
    "messages": [{
        "role": "user",
        "content": prompt_path.read_text(encoding="utf-8"),
    }],
}
request = urllib.request.Request(
    base_url + "/v1/messages",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "x-api-key": env["ANTHROPIC_AUTH_TOKEN"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    },
)
parts = []
metadata = {}
message_stopped = False
started = time.monotonic()
with urllib.request.urlopen(request, timeout=60) as response:
    for raw in response:
        if time.monotonic() - started > 600:
            raise TimeoutError("Request exceeded 600 seconds")
        line = raw.decode("utf-8").strip()
        if not line.startswith("data: "):
            continue
        event = json.loads(line[6:])
        kind = event.get("type")
        if kind == "message_start":
            metadata["model"] = event["message"]["model"]
            print("MODEL " + metadata["model"], flush=True)
        elif kind == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                parts.append(delta.get("text", ""))
        elif kind == "message_delta":
            metadata.update(event)
        elif kind == "message_stop":
            message_stopped = True
        elif kind == "error":
            raise RuntimeError("API stream error; result is incomplete")
text = "".join(parts)
complete = (
    message_stopped
    and metadata.get("model") == "glm-5.3"
    and metadata.get("delta", {}).get("stop_reason") == "end_turn"
    and bool(text.strip())
)
target = output_path if complete else output_path.with_suffix(".partial.txt")
target.write_text(text, encoding="utf-8", newline="\n")
target.with_suffix(".meta.json").write_text(
    json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print("DONE" if complete else "INCOMPLETE", flush=True)
raise SystemExit(0 if complete else 1)
```

В PowerShell, из корня репозитория (использовать новые имена результатов
для каждого запуска, чтобы не принять старый файл за свежий):

```powershell
python .tmp/glm-direct.py .tmp/prompt.txt .tmp/result-001.txt
```

Запрос идёт на `https://api.z.ai/api/anthropic/v1/messages` с заголовками
`x-api-key`, `anthropic-version: 2023-06-01`, `Content-Type: application/json`.
Таймаут сокета — 60 секунд; лимит 600 секунд проверяется при получении
строк, это не отдельный жёсткий таймер процесса. Держать запуск прикреплённым
к терминалу до завершения; не запускать дублирующий запрос во время ожидания.

## Приёмка и известные ограничения

- Нужны код выхода 0, `DONE`, модель `glm-5.3`, `stop_reason=end_turn`
  и полный пригодный результат. Затем обязательны независимая проверка
  изменений и релевантные тесты; ответ модели не заменяет их.
- Непотоковый запрос ранее истёк по таймауту 180 секунд; использовать SSE.
- Малый бюджет может уйти целиком на рассуждения. Даже при `max_tokens=48000`
  наблюдался обрыв результата. `max_tokens` и пустой/обрезанный ответ означают
  незавершённую работу; `.partial.txt` автоматически не применять.
- Не повторять неизменный неудачный запрос: сузить задачу либо запросить
  только недостающий фрагмент с необходимым контекстом.
- При сетевой ошибке или таймауте запуск завершается ошибкой; отсутствие
  нового результата не является успехом. Ключ и рассуждения не журналировать.
- HTTP 429 с кодом `1308` — лимит на 5 часов, с кодом `1310` — недельный
  (впервые 2026-09-24, сброс 2026-09-28 05:56 UTC+8). Время сброса указано в
  тексте ошибки; до него запрос не повторять — суженная повторная попытка
  относится только к устранимым сбоям (окно вывода, обрыв соединения), при
  квоте — ожидание reset либо разрешённый fallback (Astra-аудит финала №24). 2026-09-24 при `1310` владелец
  разрешил заменить исполнителя на Codex GPT-6-Sol (профиль `cw`); такую
  замену раскрывать в сообщении коммита. Второй случай `1310` — 2026-10-03,
  сброс 2026-10-05 05:56 UTC+8; повтора не было. По этой политике тест T-73
  и тесты с ремонтом T-74 написал Codex GPT-6.1-Sol (профиль `cw`); замена
  раскрыта в сообщениях коммитов `ebc343b` и `45a417a`.
- Политика восстановления (план качества 30.09, G21, по делегированию
  владельца): устранимый сбой — исчерпание окна вывода (`max_tokens`), обрыв
  соединения — допускает **одну** суженную повторную попытку; квота
  `1308`/`1310` — без повтора до reset: ожидание либо сразу fallback
  (меньший фрагмент, тот же контекст, новое имя результата); вторая неудача
  → замена исполнителя на Codex (профиль `cw`) после завершения прежнего
  процесса и проверки рабочего дерева. Замена раскрывается в сообщении
  коммита; независимые проверки и тесты сохраняются. У каждого запуска —
  run-id (имя результата), бюджет, признак завершения и артефакт;
  `.partial` не применяется.

GitHub Actions исполняют задания; CI зелёный на `45a417a` (2026-10-03,
прогон 37157492007). CI проверяет коммит после push; проверки перед коммитом
по-прежнему выполнять на Mac `deproject-mac`. Тяжёлые тесты, модели и
контейнеры на Windows не запускать.
