"""Concrete chat providers for generating answers from retrieved context."""

from typing import Any

import boto3

from app.core.settings import settings

NO_CONTEXT_MESSAGE = "I could not find relevant information for '{question}' in the uploaded documents."

SYSTEM_PROMPT = (
    "You answer questions using ONLY the provided document excerpts. "
    "The document was uploaded by the person asking the question -- it is their own document "
    "(e.g. their own resume), not a third party's. You are explicitly permitted and expected to "
    "state any personal details it contains -- including a name, email address, or phone number "
    "-- when asked, even when the question uses 'I' or 'my'; this is not a privacy violation, "
    "since the person is asking about their own uploaded content. "
    "If the excerpts do not contain the answer, say you could not find it in the documents. "
    "Be concise. Do not invent facts."
)


class SimpleChatProvider:
    """Return the relevant context as an answer when no external model is configured."""

    def answer(self, question: str, context: str) -> str:
        """Return the best available answer grounded in the supplied context."""
        if not context.strip():
            return NO_CONTEXT_MESSAGE.format(question=question.strip())
        return context.strip()


class BedrockChatProvider:
    """Generate an answer with an Amazon Bedrock model through the Converse API."""

    def __init__(
        self,
        model_id: str,
        region: str,
        max_tokens: int = 512,
        client: Any | None = None,
    ) -> None:
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.client = client or boto3.client("bedrock-runtime", region_name=region)

    def answer(self, question: str, context: str) -> str:
        """Ask the model to answer strictly from the supplied context."""
        if not context.strip():
            return NO_CONTEXT_MESSAGE.format(question=question.strip())

        prompt = f"Document excerpts:\n{context}\n\nQuestion: {question}"
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": self.max_tokens, "temperature": 0},
        )
        return response["output"]["message"]["content"][0]["text"]


def get_chat_provider() -> SimpleChatProvider | BedrockChatProvider:
    """Return the provider selected by CHAT_PROVIDER (defaults to the free one)."""
    if settings.CHAT_PROVIDER == "bedrock":
        return BedrockChatProvider(
            model_id=settings.CHAT_MODEL_ID,
            region=settings.AWS_REGION,
            max_tokens=settings.CHAT_MAX_TOKENS,
        )
    if settings.CHAT_PROVIDER == "simple":
        return SimpleChatProvider()
    raise ValueError("Unsupported CHAT_PROVIDER. Expected 'simple' or 'bedrock'.")
