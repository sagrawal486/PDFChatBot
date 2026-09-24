import asyncio

import pytest
from fastapi import HTTPException

from app.api.questions import router, ask_question
from app.services.usage_limiter import UsageLimitExceeded


class FakeRagService:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def answer(self, user_id: int, question: str, limit: int = 5):
        self.calls.append((user_id, question))
        return type(
            "Result",
            (),
            {
                "answer": "The answer is forty-two.",
                "citations": [
                    type(
                        "Citation",
                        (),
                        {
                            "content": "The answer is forty-two.",
                            "document_id": 8,
                            "chunk_index": 2,
                            "page_number": 5,
                            "score": 0.9,
                        },
                    )()
                ],
            },
        )()


class FakeLimiter:
    """Fake usage limiter recording checks and records without a database."""

    def __init__(self, exceeded: bool = False) -> None:
        self.exceeded = exceeded
        self.checked: list[int] = []
        self.recorded: list[int] = []

    def ensure_within_limit(self, user_id: int) -> None:
        self.checked.append(user_id)
        if self.exceeded:
            raise UsageLimitExceeded("Daily question limit of 30 reached. Try again later.")

    def record(self, user_id: int) -> None:
        self.recorded.append(user_id)


def test_ask_question_route_forwards_authenticated_user_and_question() -> None:
    service = FakeRagService()
    limiter = FakeLimiter()
    user = type("User", (), {"id": 42})()

    result = asyncio.run(
        ask_question(type("Request", (), {"question": "What is the answer?"})(), user, service, limiter)
    )

    assert result.answer == "The answer is forty-two."
    assert result.citations[0].document_id == 8
    assert result.citations[0].chunk_index == 2
    assert result.citations[0].page_number == 5
    assert result.citations[0].excerpt == "The answer is forty-two."
    assert service.calls == [(42, "What is the answer?")]
    assert limiter.checked == [42]
    assert limiter.recorded == [42]


def test_question_route_uses_dependency_injection() -> None:
    route = next(route for route in router.routes if route.endpoint is ask_question)
    dependency = next(
        dependency
        for dependency in route.dependant.dependencies
        if dependency.call.__name__ == "get_rag_service"
    )

    assert dependency.call.__name__ == "get_rag_service"


def test_question_route_rejects_empty_questions() -> None:
    service = FakeRagService()
    limiter = FakeLimiter()
    user = type("User", (), {"id": 42})()

    with pytest.raises(HTTPException) as error:
        asyncio.run(ask_question(type("Request", (), {"question": " "})(), user, service, limiter))

    assert error.value.status_code == 400
    assert limiter.checked == []


def test_question_route_rejects_when_daily_limit_exceeded() -> None:
    service = FakeRagService()
    limiter = FakeLimiter(exceeded=True)
    user = type("User", (), {"id": 42})()

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            ask_question(type("Request", (), {"question": "What is the answer?"})(), user, service, limiter)
        )

    assert error.value.status_code == 429
    assert service.calls == []
