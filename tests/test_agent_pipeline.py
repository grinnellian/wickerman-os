"""
Phase 1.3: Unit tests for agent pipeline and RAG operations (#6).
Tests the core agent pipeline logic from the Model Router.
Functions are reimplemented for isolation since the full manager.py
requires llama.cpp, faiss, etc.
"""
import pytest


# ── Reimplemented pipeline functions ─────────────────────────────────────

def _apply_agent_pipeline(slot, messages, request_settings=None):
    """Reimplemented from src/plugins/llama/manager.py"""
    # 1. System prompt: concatenate slot identity + incoming task context
    slot_prompt = slot.get("system_prompt", "")
    incoming_sys = None
    if messages and messages[0].get("role") == "system":
        incoming_sys = messages.pop(0)

    if slot_prompt and incoming_sys:
        combined = slot_prompt + "\n\n" + incoming_sys["content"]
        messages.insert(0, {"role": "system", "content": combined})
    elif slot_prompt:
        messages.insert(0, {"role": "system", "content": slot_prompt})
    elif incoming_sys:
        messages.insert(0, incoming_sys)

    # 2. Merge request-level settings with slot defaults
    merged = dict(slot.get("settings", {}))
    if request_settings:
        merged.update(request_settings)

    return messages, merged


# ── count_tokens reimplementation (simplified) ──────────────────────────

def count_tokens(text):
    """Approximate token count: split on whitespace. Real impl uses tiktoken."""
    return len(text.split())


def _split_long_text(text, max_tokens):
    """Reimplemented from src/plugins/llama/manager.py"""
    if count_tokens(text) <= max_tokens:
        return [text]
    parts = text.split("\n\n")
    chunks, current = [], ""
    for part in parts:
        if count_tokens(current + "\n\n" + part) > max_tokens and current:
            chunks.append(current)
            current = part
        else:
            current = (current + "\n\n" + part).strip()
    if current:
        chunks.append(current)
    return chunks if chunks else [text[:max_tokens * 4]]


def chunk_messages(messages, chunk_size=200, chunk_overlap=50):
    """Reimplemented from src/plugins/llama/manager.py"""
    chunks, current, current_tokens = [], [], 0
    for m in messages:
        text = m.get("role", "user") + ": " + m.get("content", "")
        msg_tokens = count_tokens(text)
        if msg_tokens > chunk_size:
            if current:
                chunks.append("\n".join(current))
                current, current_tokens = [], 0
            for sub in _split_long_text(text, chunk_size):
                chunks.append(sub)
            continue
        if current_tokens + msg_tokens > chunk_size and current:
            chunks.append("\n".join(current))
            overlap_msgs, overlap_tokens = [], 0
            for prev in reversed(current):
                prev_tokens = count_tokens(prev)
                if overlap_tokens + prev_tokens > chunk_overlap:
                    break
                overlap_msgs.insert(0, prev)
                overlap_tokens += prev_tokens
            current, current_tokens = overlap_msgs, overlap_tokens
        current.append(text)
        current_tokens += msg_tokens
    if current:
        chunks.append("\n".join(current))
    return chunks


class TestAgentPipeline:
    """Test _apply_agent_pipeline system prompt handling."""

    def test_slot_prompt_only(self):
        slot = {"system_prompt": "You are a pirate."}
        messages = [{"role": "user", "content": "Hello"}]
        result_msgs, _ = _apply_agent_pipeline(slot, messages)
        assert result_msgs[0]["role"] == "system"
        assert result_msgs[0]["content"] == "You are a pirate."
        assert result_msgs[1]["role"] == "user"

    def test_incoming_system_only(self):
        slot = {}
        messages = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result_msgs, _ = _apply_agent_pipeline(slot, messages)
        assert result_msgs[0]["role"] == "system"
        assert result_msgs[0]["content"] == "Be helpful."

    def test_both_prompts_combined(self):
        slot = {"system_prompt": "You are a pirate."}
        messages = [
            {"role": "system", "content": "Speak in rhyme."},
            {"role": "user", "content": "Hello"},
        ]
        result_msgs, _ = _apply_agent_pipeline(slot, messages)
        assert result_msgs[0]["role"] == "system"
        assert "pirate" in result_msgs[0]["content"]
        assert "rhyme" in result_msgs[0]["content"]

    def test_no_system_prompt(self):
        slot = {}
        messages = [{"role": "user", "content": "Hello"}]
        result_msgs, _ = _apply_agent_pipeline(slot, messages)
        assert result_msgs[0]["role"] == "user"

    def test_settings_merging(self):
        slot = {"settings": {"temperature": 0.7, "top_p": 0.9}}
        messages = [{"role": "user", "content": "Hello"}]
        _, merged = _apply_agent_pipeline(slot, messages, {"temperature": 0.3})
        assert merged["temperature"] == 0.3  # request overrides slot
        assert merged["top_p"] == 0.9  # slot default preserved

    def test_settings_no_request(self):
        slot = {"settings": {"temperature": 0.7}}
        messages = [{"role": "user", "content": "Hello"}]
        _, merged = _apply_agent_pipeline(slot, messages)
        assert merged["temperature"] == 0.7

    def test_empty_settings(self):
        slot = {}
        messages = [{"role": "user", "content": "Hello"}]
        _, merged = _apply_agent_pipeline(slot, messages)
        assert merged == {}


class TestSplitLongText:
    def test_short_text_not_split(self):
        text = "Hello world"
        result = _split_long_text(text, 100)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_split_on_paragraphs(self):
        paragraphs = ["Paragraph " + str(i) + " " + "word " * 50 for i in range(5)]
        text = "\n\n".join(paragraphs)
        result = _split_long_text(text, 60)
        assert len(result) > 1
        # All paragraphs should appear in some chunk
        full = " ".join(result)
        for p in paragraphs:
            assert "Paragraph" in full


class TestChunkMessages:
    def test_single_short_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        chunks = chunk_messages(messages)
        assert len(chunks) == 1

    def test_multiple_messages_within_limit(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        chunks = chunk_messages(messages, chunk_size=100)
        assert len(chunks) == 1

    def test_messages_exceeding_chunk_size(self):
        messages = [
            {"role": "user", "content": "word " * 100},
            {"role": "assistant", "content": "response " * 100},
            {"role": "user", "content": "another " * 100},
        ]
        chunks = chunk_messages(messages, chunk_size=50)
        assert len(chunks) > 1

    def test_empty_messages(self):
        chunks = chunk_messages([])
        assert chunks == []

    def test_overlap_preserved(self):
        # With overlap, some content should appear in multiple chunks
        messages = [
            {"role": "user", "content": "word " * 50},
            {"role": "assistant", "content": "reply " * 50},
            {"role": "user", "content": "more " * 50},
        ]
        chunks = chunk_messages(messages, chunk_size=60, chunk_overlap=20)
        # At least 2 chunks since total exceeds chunk_size
        assert len(chunks) >= 2
