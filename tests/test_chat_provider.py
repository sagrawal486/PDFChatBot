"""Tests for chat providers without contacting AWS."""

import pytest

from app.services import chat_provider
from app.services.chat_provider import BedrockChatProvider, SimpleChatProvider


class FakeBedrockClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {"output": {"message": {"content": [{"text": "Forty-two."}]}}}


def test_bedrock_provider_sends_grounded_prompt_and_limits_tokens() -> None:
    client = FakeBedrockClient()
    provider = BedrockChatProvider("model-x", "ap-south-1", max_tokens=100, client=client)

    answer = provider.answer("What is the answer?", "The answer is forty-two.")

    call = client.calls[0]
    assert answer == "Forty-two."
    assert call["modelId"] == "model-x"
    assert call["inferenceConfig"]["maxTokens"] == 100
    assert "ONLY" in call["system"][0]["text"]
    assert "The answer is forty-two." in call["messages"][0]["content"][0]["text"]


def test_bedrock_system_prompt_permits_answering_first_person_questions() -> None:
    """Regression test: Nova Micro refused to state a name/email/phone found in the
    context whenever the question used 'my' (e.g. "what is my email"), even though the
    same fact was answered correctly when phrased in third person. Empirically confirmed
    against the real model; fixed by telling it the document is the asker's own and that
    stating their own details on request isn't a privacy violation. This test guards the
    prompt wording that fix depends on -- it can't catch a regression in the model's
    behavior itself, only in this system prompt accidentally losing that instruction.
    """
    client = FakeBedrockClient()
    provider = BedrockChatProvider("model-x", "ap-south-1", client=client)

    provider.answer("What is my email?", "some context")

    system_text = client.calls[0]["system"][0]["text"]
    assert "'I' or 'my'" in system_text
    assert "not a privacy violation" in system_text


def test_bedrock_provider_skips_the_model_call_without_context() -> None:
    client = FakeBedrockClient()
    provider = BedrockChatProvider("model-x", "ap-south-1", client=client)

    answer = provider.answer("Anything?", "   ")

    assert client.calls == []
    assert "could not find" in answer


def test_get_chat_provider_defaults_to_free_provider(monkeypatch) -> None:
    monkeypatch.setattr(chat_provider.settings, "CHAT_PROVIDER", "simple")

    assert isinstance(chat_provider.get_chat_provider(), SimpleChatProvider)


def test_get_chat_provider_rejects_unknown_provider(monkeypatch) -> None:
    monkeypatch.setattr(chat_provider.settings, "CHAT_PROVIDER", "nope")

    with pytest.raises(ValueError):
        chat_provider.get_chat_provider()
