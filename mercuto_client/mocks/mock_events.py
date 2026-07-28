import logging
import uuid
from datetime import datetime
from typing import Optional

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.events import Axle, EditVehicleIn, Event, Tag, Vehicle

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
            user_edited=False,
            tags=tags or [],
            vehicles=[],
            artifacts=[],
            processing_status='complete'
        )
        self._events[code] = event
        return event

    def get_nearest_event(self, project: str, to: datetime,
                          maximum_delta: Optional[float] = None) -> Event:
        candidates = [e for e in self._events.values() if e.project == project]
        if not candidates:
            raise MercutoHTTPException("No events found", 404)
        nearest = min(candidates, key=lambda e: abs((e.start_time - to).total_seconds()))
        nearest_dist = abs((nearest.start_time - to).total_seconds())
        if maximum_delta is not None and nearest_dist > maximum_delta:
            raise MercutoHTTPException("No events found within the specified time range", 404)
        return nearest

    def get_event(self, event: str) -> Event:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        return self._events[event]

    def update_event(self, event: str,
                     start_time: datetime,
                     end_time: datetime,
                     tags: list[Tag],
                     vehicles: list[EditVehicleIn]) -> Event:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        event_model = self._events[event]
        new_vehicles = [
            Vehicle(
                vehicle_index=v.vehicle_index,
                velocity_ms=v.velocity_ms,
                reference_position_m=v.reference_position_m,
                axles=[
                    Axle(
                        axle_index=i,
                        position_m=0.0,
                        crossing_time=a.crossing_time,
                        mass_kg=None,
                        confidence=None,
                    )
                    for i, a in enumerate(v.axles)
                ],
            )
            for v in vehicles
        ]
        updated = event_model.model_copy(update={
            'start_time': start_time,
            'end_time': end_time,
            'tags': tags,
            'vehicles': new_vehicles,
        })
        self._events[event] = updated
        return updated

    def delete_event(self, event: str) -> None:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        del self._events[event]

    def replace_event_tags(self, event: str, tags: list[Tag]) -> None:
        if event not in self._events:
            raise MercutoHTTPException("Event not found", 404)
        event_model = self._events[event]
        self._events[event] = event_model.model_copy(update={'tags': list(tags)})

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
