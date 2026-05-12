from __future__ import annotations

from app.models.schemas import FeedbackEvent


class FeedbackStore:
    def __init__(self) -> None:
        self._events: list[FeedbackEvent] = []

    def append(self, event: FeedbackEvent) -> int:
        self._events.append(event)
        return len(self._events)

    def all(self) -> list[FeedbackEvent]:
        return list(self._events)


feedback_store = FeedbackStore()

