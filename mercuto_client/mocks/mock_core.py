import logging
import uuid
from datetime import datetime
from typing import Optional

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.core import Event, ItemCode, MercutoCoreService
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)


class MockMercutoCoreService(MercutoCoreService, metaclass=EnforceOverridesMeta):
    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client)
        self._events: dict[str, Event] = {}

    def create_event(self, project: str, start_time: datetime, end_time: datetime) -> Event:
        event = Event(code=str(uuid.uuid4()), project=ItemCode(code=project), start_time=start_time, end_time=end_time, objects=[], tags=[])
        self._events[event.code] = event
        return event

    def get_event(self, event: str) -> Event:
        if event not in self._events:
            raise MercutoHTTPException(status_code=404, message=f"Event {event} not found")
        return self._events[event]

    def list_events(self, project: str,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: Optional[int] = None, offset: Optional[int] = 0,
                    ascending: bool = True) -> list[Event]:
        filtered = [event for event in self._events.values() if event.project.code == project]
        if start_time is not None:
            filtered = [event for event in filtered if event.start_time >= start_time]
        if end_time is not None:
            filtered = [event for event in filtered if event.end_time <= end_time]
        filtered.sort(key=lambda e: e.start_time, reverse=not ascending)
        if offset is not None:
            filtered = filtered[offset:]
        if limit is not None:
            filtered = filtered[:limit]
        return filtered
