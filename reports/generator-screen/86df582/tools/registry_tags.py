"""Read the Ollama registry manifests of the Qwen3 4B tags; print each manifest's SHA-256
(Ollama's model digest) and its model layer, without pulling anything."""

import hashlib
import json
import urllib.request

TAGS = ["4b", "4b-thinking", "4b-thinking-2507-q4_K_M", "4b-instruct", "4b-instruct-2507-q4_K_M"]
for tag in TAGS:
    request = urllib.request.Request(
        f"https://registry.ollama.ai/v2/library/qwen3/manifests/{tag}",
        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
    )
    try:
        body = urllib.request.urlopen(request, timeout=30).read()
    except Exception as exc:  # noqa: BLE001 - report and go on
        print(tag, "ERR", exc)
        continue
    manifest = json.loads(body)
    layers = {layer["mediaType"].rsplit(".", 1)[-1]: layer for layer in manifest["layers"]}
    model = layers.get("model", {})
    print(
        tag,
        hashlib.sha256(body).hexdigest()[:12],
        model.get("digest", "")[:19],
        model.get("size"),
        sorted(layers),
    )
