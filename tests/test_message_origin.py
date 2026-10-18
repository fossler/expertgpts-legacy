"""Tests for recording which LLM produced an assistant message."""

import pytest

from lib.storage import chat_history_manager as chm


@pytest.fixture
def history_dir(tmp_path, monkeypatch):
    """Point the chat history at a temporary directory."""
    monkeypatch.setattr(chm, "get_chat_history_dir", lambda: tmp_path)
    return tmp_path


@pytest.mark.unit
def test_assistant_message_records_provider_and_model():
    assert chm.assistant_message("Hi", "openai", "gpt-6.1-sol") == {
        "role": "assistant",
        "content": "Hi",
        "provider": "openai",
        "model": "gpt-6.1-sol",
    }


@pytest.mark.unit
def test_provider_and_model_survive_save_and_load(history_dir):
    messages = [
        {"role": "user", "content": "Q"},
        chm.assistant_message("A1", "deepseek", "deepseek-flash"),
        chm.assistant_message("A2", "openai", "gpt-6.1-sol"),
        {"role": "assistant", "content": "older answer without origin"},
    ]
    assert chm.save_chat_history("1001_x", messages)
    loaded = chm.load_chat_history("1001_x")
    assert loaded == messages


@pytest.mark.unit
def test_missing_origin_is_not_stored_as_empty(history_dir):
    chm.save_chat_history("1001_x", [chm.assistant_message("A", None, None)])
    loaded = chm.load_chat_history("1001_x")
    assert [{k: v for k, v in m.items() if k != "timestamp"} for m in loaded] == [
        {"role": "assistant", "content": "A"}
    ]


@pytest.mark.unit
def test_timestamp_is_kept_across_saves(history_dir):
    first = {"role": "user", "content": "Q"}
    chm.save_chat_history("1001_x", [first])
    stamp = first["timestamp"]

    # Reload like an app restart, then save again with a new message
    messages = chm.load_chat_history("1001_x")
    messages.append(chm.assistant_message("A", "openai", "gpt-6.1-sol"))
    chm.save_chat_history("1001_x", messages)

    loaded = chm.load_chat_history("1001_x")
    assert loaded[0]["timestamp"] == stamp
    assert loaded[1]["timestamp"] >= stamp
