"""Coordinator profile must never route PS2 work to swarm mode."""

import asyncio

import hive.leader as leader_module
from hive.leader import Leader


class _Memory:
    def __init__(self):
        self.messages = []

    def add_message(self, role, content):
        self.messages.append((role, content))


def test_coordinator_profile_forces_single_agent(monkeypatch):
    monkeypatch.setattr(leader_module, "HIVE_AGENT_PROFILE", "coordinator")

    leader = Leader.__new__(Leader)

    async def forbidden_route(_message):
        raise AssertionError("_route_task must not run in coordinator mode")

    async def fake_single(*_args, **_kwargs):
        return "single-agent response"

    leader._route_task = forbidden_route
    leader._run_single_agent = fake_single

    memory = _Memory()
    response = asyncio.run(
        leader.handle_message("check my inbox", "session", memory, None)
    )
    assert response == "single-agent response"
    assert memory.messages[0][0] == "user"
    assert memory.messages[-1][0] == "assistant"
