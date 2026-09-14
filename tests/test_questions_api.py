import asyncio

import pytest
from fastapi import HTTPException

from app.api.questions import router, ask_question


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
                        {"content": "The answer is forty-two.", "document_id": 8, "chunk_index": 2},
                    )()
                ],
            },
        )()


def test_ask_question_route_forwards_authenticated_user_and_question() -> None:
    service = FakeRagService()
    user = type("User", (), {"id": 42})()

    result = asyncio.run(ask_question(type("Request", (), {"question": "What is the answer?"})(), user, service))

    assert result.answer == "The answer is forty-two."
    assert result.citations[0].document_id == 8
    assert result.citations[0].chunk_index == 2
    assert service.calls == [(42, "What is the answer?")]


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
    user = type("User", (), {"id": 42})()

    with pytest.raises(HTTPException) as error:
        asyncio.run(ask_question(type("Request", (), {"question": " "})(), user, service))

    assert error.value.status_code == 400
