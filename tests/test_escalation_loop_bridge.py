"""A graph worker must persist on the API loop owning asyncpg connections."""
import asyncio

import pytest

from services.escalation import EscalationService
from utils.event_loop import set_main_loop


@pytest.mark.asyncio
async def test_graph_worker_escalation_uses_registered_api_loop(monkeypatch):
    owner = asyncio.get_running_loop()
    service = EscalationService()

    async def create(**kwargs):
        assert asyncio.get_running_loop() is owner, "asyncpg pool used on a foreign loop"
        return kwargs["question"]

    monkeypatch.setattr(service, "create_escalation", create)
    set_main_loop(owner)
    try:
        assert await asyncio.to_thread(service.create_escalation_sync, question="handoff") == "handoff"
    finally:
        set_main_loop(None)


@pytest.mark.asyncio
async def test_sync_wrapper_refuses_to_block_the_registered_api_loop():
    set_main_loop(asyncio.get_running_loop())
    try:
        with pytest.raises(RuntimeError, match="await"):
            EscalationService().create_escalation_sync(question="handoff")
    finally:
        set_main_loop(None)
