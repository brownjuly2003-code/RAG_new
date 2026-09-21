from __future__ import annotations

import hashlib
import json

from resolution.contracts.models import ResolutionContract


def canonical_contract_json(contract: ResolutionContract) -> str:
    """Return the versioned contract payload in deterministic JSON form."""
    payload = contract.model_dump(mode="json", by_alias=True, exclude_none=False)
    if contract.response_shape is None:
        # Shape-less contracts predate the field; dropping the unused key keeps
        # the v0.1.0 canonical digest byte-identical.
        payload.pop("response_shape", None)
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def contract_digest(contract: ResolutionContract) -> str:
    """Return the SHA-256 identity of the canonical contract payload."""
    canonical = canonical_contract_json(contract).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = ["canonical_contract_json", "contract_digest"]
