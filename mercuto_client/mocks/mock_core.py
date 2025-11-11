import logging
import uuid
from datetime import datetime

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

    def list_events(self, project: str) -> list[Event]:
        return [event for event in self._events.values() if event.project.code == project]
