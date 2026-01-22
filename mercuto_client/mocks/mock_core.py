import logging
import uuid
from datetime import datetime
from datetime import timezone as py_timezone
from typing import Optional

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.core import (Device, DeviceChannel, DeviceType, Event, ItemCode,
                            MercutoCoreService, Project, ProjectStatus)
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)


class MockMercutoCoreService(MercutoCoreService, metaclass=EnforceOverridesMeta):
    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client)
        self._events: dict[str, Event] = {}
        self._projects: dict[str, Project] = {}
        self._devices: dict[str, Device] = {}

    def get_project(self, code: str) -> Project:
        if code not in self._projects:
            raise MercutoHTTPException(status_code=404, message=f"Project {code} not found")
        return self._projects[code]

    def create_project(self, name: str, project_number: str, description: str, tenant: str,
                       timezone: str, latitude: Optional[float] = None,
                       longitude: Optional[float] = None) -> Project:
        project = Project(
            code=str(uuid.uuid4()),
            name=name,
            project_number=project_number,
            active=True,
            description=description,
            tenant=tenant,
            timezone=timezone,
            latitude=latitude,
            longitude=longitude,
            display_timezone=timezone,
            status=ProjectStatus(last_ping=None, ip_address=None),
            commission_date=datetime(2020, 1, 1, tzinfo=py_timezone.utc)
        )
        self._projects[project.code] = project
        return project

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

    def list_devices(self, project_code: str, limit: int, offset: int) -> list[Device]:
        return [device for device in self._devices.values() if device.project.code == project_code][offset:offset+limit]

    def get_device(self, device_code: str) -> Device:
        if device_code not in self._devices:
            raise MercutoHTTPException(status_code=404, message=f"Device {device_code} not found")
        return self._devices[device_code]

    def create_device(self,
                      project_code: str,
                      label: str,
                      device_type_code: str,
                      groups: list[str],
                      location_description: Optional[str] = None,
                      channels: Optional[list[DeviceChannel]] = None,
                      latitude: Optional[float] = None,
                      longitude: Optional[float] = None,
                      altitude: Optional[float] = None
                      ) -> Device:
        device = Device(
            code=str(uuid.uuid4()),
            project=ItemCode(code=project_code),
            label=label,
            device_type=DeviceType(
                code=device_type_code,
                description="A mock device type for testing",
                manufacturer="Mock Manufacturer",
                model_number="Model X",

            ),
            groups=groups,
            location_description=location_description,
            channels=channels or [],
        )
        self._devices[device.code] = device
        return device
