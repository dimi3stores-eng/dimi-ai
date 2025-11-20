"""Regression coverage for hands tool helpers."""

from pathlib import Path
import sys
import types


class _FakeResponse:
    def __init__(self):
        self.text = ""

    def raise_for_status(self):
        return None


def _fake_get(url, **kwargs):
    return _FakeResponse()


# Provide a lightweight requests stub to satisfy imports when wheels are unavailable.
sys.modules.setdefault("requests", types.SimpleNamespace(get=_fake_get))

import agent_tools


def setup_module(module):
    """Isolate tool storage so tests do not pollute real data."""
    tmp_dir = Path("/tmp/dimi-ai-tests")
    tmp_dir.mkdir(exist_ok=True)
    module._tmp_hands_path = tmp_dir / "hands.json"
    # Point the module-level path at a throwaway location for all helpers.
    agent_tools.HANDS_PATH = module._tmp_hands_path
    if agent_tools.HANDS_PATH.exists():
        agent_tools.HANDS_PATH.unlink()


def teardown_module(module):
    if module._tmp_hands_path.exists():
        module._tmp_hands_path.unlink()


def test_create_and_list_hands_session_scope():
    reply = agent_tools._create_hand("Lefty", "Draft copy", session_id="s1")
    assert "Created hand" in reply

    listed_for_owner = agent_tools._list_hands(session_id="s1")
    assert "scope: session" in listed_for_owner

    listed_shared = agent_tools._list_hands(session_id="other")
    assert "scope: shared" in listed_shared


def test_add_update_and_remove_tasks_with_validation():
    agent_tools._create_hand("Righty", "Ship tasks", session_id="s2")
    add_reply = agent_tools._add_task_to_hand("Righty", "Write brief", "first draft", session_id="s2")
    assert "task id" in add_reply

    list_reply = agent_tools._list_tasks("Righty", session_id="s2")
    assert "[todo] Write brief" in list_reply

    update_reply = agent_tools._update_task("Righty", "write brief", status="done", detail="finalized", session_id="s2")
    assert "Updated task" in update_reply

    # Ensure remove gracefully rejects missing identifiers instead of crashing.
    missing_ref = agent_tools._remove_task("Righty", "", session_id="s2")
    assert missing_ref == "Task reference is required."

    remove_reply = agent_tools._remove_task("Righty", "write brief", session_id="s2")
    assert "Removed task" in remove_reply
