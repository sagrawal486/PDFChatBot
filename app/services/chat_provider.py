"""Concrete chat providers for generating answers from retrieved context."""

from app.core.settings import settings


class SimpleChatProvider:
    """Return the relevant context as an answer when no external model is configured."""

    def answer(self, question: str, context: str) -> str:
        """Return the best available answer grounded in the supplied context."""
        normalized_question = question.strip()
        if not context.strip():
            return (
                f"I could not find relevant information for '{normalized_question}' "
                "in the uploaded documents."
            )
        return context.strip()


class BedrockChatProvider:
    """Generate an answer with an injected Bedrock chat model when configured."""

    def __init__(self, model_id: str, region: str, client=None) -> None:
        self.model_id = model_id
        self.region = region
        self.client = client

    def answer(self, question: str, context: str) -> str:
        """Use the configured Bedrock model to answer the question from context."""
        if not context.strip():
            return (
                f"I could not find relevant information for '{question.strip()}' "
                "in the uploaded documents."
            )

        if self.client is None:
            return SimpleChatProvider().answer(question, context)

        prompt = f"Question: {question}\n\nContext:\n{context}"
        response = self.client.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
        )
        return response["output"]["message"]["content"][0]["text"]


def get_chat_provider() -> SimpleChatProvider | BedrockChatProvider:
    """Return the configured chat provider without requiring AWS when it is unavailable."""
    if settings.OPENAI_API_KEY:
        return SimpleChatProvider()
    return SimpleChatProvider()
