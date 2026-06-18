import ipaddress
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.assets import (Device, DeviceChannel, Healthcheck,
                              MercutoAssetService, MetadataEntry, Project)
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)
UTC = timezone.utc


class MockMercutoAssetService(MercutoAssetService, metaclass=EnforceOverridesMeta):
    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client, path='/mock-assets-service-method-not-implemented')
        self._projects: dict[str, Project] = {}
        self._devices: dict[str, Device] = {}

    def healthcheck(self) -> Healthcheck:
        return Healthcheck(status='ok')

    def ping_project(self, project: str, ip_address: str) -> None:
        self.get_project(project)
        try:
            ipaddress.ip_address(ip_address)
        except ValueError as exc:
            raise MercutoHTTPException("Not a valid IP address", 400) from exc

    # --- Projects routes ---

    def list_projects(self, limit: int = 100, offset: int = 0) -> list[Project]:
        return sorted(self._projects.values(), key=lambda p: p.code)[offset:offset + limit]

    def create_project(
        self,
        tenant: str,
        name: str,
        description: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        timezone: Optional[str] = None,
        commissioned_at: Optional[datetime] = None,
        is_active: bool = True,
        project_number: Optional[str] = None,
    ) -> Project:
        code = str(uuid.uuid4())
        now = datetime.now(UTC)
        project = Project(
            code=code,
            tenant=tenant,
            name=name,
            description=description,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            commissioned_at=commissioned_at,
            is_active=is_active,
            created_at=now,
            updated_at=now,
            project_number=project_number,
        )
        self._projects[code] = project
        return project

    def get_project(self, code: str) -> Project:
        project = self._projects.get(code)
        if project is None:
            raise MercutoHTTPException("Project not found", 404)
        return project

    def update_project(
        self,
        code: str,
        name: str,
        description: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        timezone: Optional[str] = None,
        commissioned_at: Optional[datetime] = None,
        is_active: bool = True,
    ) -> Project:
        project = self.get_project(code)
        updated = project.model_copy(update={
            'name': name,
            'description': description,
            'latitude': latitude,
            'longitude': longitude,
            'timezone': timezone,
            'commissioned_at': commissioned_at,
            'is_active': is_active,
            'updated_at': datetime.now(UTC),
        })
        self._projects[code] = updated
        return updated

    def delete_project(self, code: str) -> None:
        self.get_project(code)
        if any(device.project == code for device in self._devices.values()):
            raise MercutoHTTPException("Cannot delete project while it still has devices", 409)
        del self._projects[code]

    # --- Devices routes ---

    def list_devices(self, project: str, limit: int = 100, offset: int = 0) -> list[Device]:
        self.get_project(project)
        devices = sorted([d for d in self._devices.values() if d.project == project], key=lambda d: d.label)
        return devices[offset:offset + limit]

    def create_device(
        self,
        project: str,
        label: str,
        device_type: str,
        parent: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        metadata: Optional[dict[str, MetadataEntry]] = None,
        channels: Optional[list[DeviceChannel]] = None,
    ) -> Device:
        self.get_project(project)
        if parent is not None:
            parent_device = self._devices.get(parent)
            if parent_device is None:
                raise MercutoHTTPException("Parent device not found", 404)
            if parent_device.project != project:
                raise MercutoHTTPException("Parent device must belong to the same project", 422)

        code = str(uuid.uuid4())
        now = datetime.now(UTC)
        device = Device(
            code=code,
            project=project,
            label=label,
            device_type=device_type,
            parent=parent,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            metadata=metadata or {},
            channels=[
                DeviceChannel(field=channel.field, channel=channel.channel)
                for channel in (channels or [])
            ],
            children=[],
            created_at=now,
            updated_at=now,
        )
        self._devices[code] = device

        if parent is not None:
            self._sync_parent_children(parent)

        return device

    def get_device(self, code: str) -> Device:
        device = self._devices.get(code)
        if device is None:
            raise MercutoHTTPException("Device not found", 404)
        return device

    def update_device(
        self,
        code: str,
        label: str,
        parent: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        metadata: Optional[dict[str, MetadataEntry]] = None,
        channels: Optional[list[DeviceChannel]] = None,
    ) -> Device:
        existing = self.get_device(code)

        if parent is not None:
            parent_device = self._devices.get(parent)
            if parent_device is None:
                raise MercutoHTTPException("Parent device not found", 404)
            if parent_device.project != existing.project:
                raise MercutoHTTPException("Parent device must belong to the same project", 422)

        updated = existing.model_copy(update={
            'label': label,
            'parent': parent,
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude,
            'metadata': metadata or {},
            'channels': [
                DeviceChannel(field=channel.field, channel=channel.channel)
                for channel in (channels or [])
            ],
            'updated_at': datetime.now(UTC),
        })

        self._devices[code] = updated

        # Parent-child links are derived, so refresh both old and new parent children lists.
        if existing.parent is not None:
            self._sync_parent_children(existing.parent)
        if parent is not None:
            self._sync_parent_children(parent)

        return updated

    def delete_device(self, code: str) -> None:
        device = self.get_device(code)
        if any(d.parent == code for d in self._devices.values()):
            raise MercutoHTTPException("Cannot delete device while it still has child devices", 409)
        del self._devices[code]
        if device.parent is not None:
            self._sync_parent_children(device.parent)

    def _sync_parent_children(self, parent_code: str) -> None:
        parent = self._devices.get(parent_code)
        if parent is None:
            return
        children = sorted([d.code for d in self._devices.values() if d.parent == parent_code])
        self._devices[parent_code] = parent.model_copy(update={'children': children})
