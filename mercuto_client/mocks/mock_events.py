import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.events import Event, Tag

logger = logging.getLogger(__name__)


class MockMercutoEventService:
    """
    Note: This mock does NOT use EnforceOverridesMeta because MercutoEventService
    is not designed for single-inheritance override enforcement. Instead it provides
    a standalone in-memory implementation of the same interface.
    """

    def __init__(self, client: 'MercutoClient') -> None:
        self._client = client
        self._events: dict[str, Event] = {}

    # ── Events ───────────────────────────────────────────

    def list_events(self, project: str,
                    limit: int = 50,
                    offset: int = 0,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    ascending: bool = False) -> list[Event]:
        items = [e for e in self._events.values() if e.project == project]
        if start_time is not None:
            items = [e for e in items if e.start_time >= start_time]
        if end_time is not None:
            items = [e for e in items if e.start_time <= end_time]
        items.sort(key=lambda e: e.start_time, reverse=not ascending)
        return items[offset:offset + limit]

    def create_event(self, project: str,
                     start_time: datetime,
                     end_time: datetime,
                     tags: Optional[list[Tag]] = None) -> Event:
        code = f"EVT-{uuid.uuid4().hex[:12]}"
        event = Event(
            project=project,
            code=code,
            start_time=start_time,
            end_time=end_time,
            tags=tags or [],
            vehicles=[],
            artifacts=[],
        )
        self._events[code] = event
        return event

    def get_nearest_event(self, project: str, to: datetime) -> Event:
        candidates = [e for e in self._events.values() if e.project == project]
        if not candidates:
            raise MercutoHTTPException("No events found", 404)
        return min(candidates, key=lambda e: min(abs((e.start_time - to).total_seconds()),
                                                 abs((e.end_time - to).total_seconds())))

    def get_event(self, event: str) -> Event:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        return self._events[event]

    def update_event(self, event: str,
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None,
                     tags: Optional[list[Tag]] = None) -> Event:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        event_model = self._events[event]
        updates: dict[str, Any] = {}
        if start_time is not None:
            updates['start_time'] = start_time
        if end_time is not None:
            updates['end_time'] = end_time
        if tags is not None:
            updates['tags'] = tags
        updated = event_model.model_copy(update=updates)
        self._events[event] = updated
        return updated

    def delete_event(self, event: str) -> None:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        del self._events[event]

    def set_event_tag(self, event: str, tag_name: str,
                      tag_value: Any = None) -> None:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        event_model = self._events[event]
        tags = [t for t in event_model.tags if t.tag_name != tag_name]
        tags.append(Tag(tag_name=tag_name, tag_value=tag_value))
        self._events[event] = event_model.model_copy(update={'tags': tags})

    def get_next_event(self, event: str, direction: str, step: int = 1) -> Event:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        event_model = self._events[event]
        candidates = [e for e in self._events.values() if e.project == event_model.project]
        if direction == "forward":
            candidates = sorted(
                [e for e in candidates if e.start_time > event_model.start_time],
                key=lambda e: e.start_time,
            )
        else:
            candidates = sorted(
                [e for e in candidates if e.start_time < event_model.start_time],
                key=lambda e: e.start_time,
                reverse=True,
            )
        idx = step - 1
        if idx >= len(candidates):
            raise MercutoHTTPException("No adjacent event found", 404)
        return candidates[idx]
