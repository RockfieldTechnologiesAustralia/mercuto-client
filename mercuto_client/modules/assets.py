from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import Field, TypeAdapter, model_validator

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import PayloadType
from ._util import BaseModel


class Project(BaseModel):
    code: str
    tenant: str
    name: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    commissioned_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    project_number: Optional[int] = None


class ChannelIn(BaseModel):
    field: str
    channel: str


class ChannelOut(BaseModel):
    field: str
    channel: str


class MetadataEntry(BaseModel):
    data_type: str
    is_list: bool = False
    value: str | int | float | bool | None = None
    values: list[str | int | float | bool] | None = None

    @model_validator(mode='after')
    def validate_value_shape(self) -> 'MetadataEntry':
        if self.is_list:
            if self.values is None:
                raise ValueError("`values` is required when `is_list` is true")
            if self.value is not None:
                raise ValueError("`value` must be null when `is_list` is true")
        else:
            if self.value is None:
                raise ValueError("`value` is required when `is_list` is false")
            if self.values is not None:
                raise ValueError("`values` must be null when `is_list` is false")
        return self


class Device(BaseModel):
    code: str
    project: str
    label: str
    device_type: str
    parent: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    metadata: dict[str, MetadataEntry] = Field(default_factory=dict)
    channels: list[ChannelOut] = []
    children: list[str] = []
    created_at: datetime
    updated_at: datetime


class Healthcheck(BaseModel):
    status: str


_ProjectListAdapter = TypeAdapter(list[Project])
_DeviceListAdapter = TypeAdapter(list[Device])


class MercutoAssetService:
    def __init__(self, client: 'MercutoClient', path: str = '/assets') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", 'GET')
        return Healthcheck.model_validate_json(r.text)

    def ping_project(self, code: str, ip_address: str) -> None:
        payload: PayloadType = {'ip_address': ip_address}
        self._client.request(f"{self._path}/projects/{code}/ping", 'POST', json=payload)

    # --- Projects routes ---

    def list_projects(self) -> list[Project]:
        r = self._client.request(f"{self._path}/projects", 'GET')
        return _ProjectListAdapter.validate_json(r.text)

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
        project_number: Optional[int] = None,
    ) -> Project:
        payload: PayloadType = {
            'tenant': tenant,
            'name': name,
            'description': description,
            'latitude': latitude,
            'longitude': longitude,
            'timezone': timezone,
            'commissioned_at': commissioned_at.isoformat() if commissioned_at is not None else None,
            'is_active': is_active,
            'project_number': project_number,
        }
        r = self._client.request(f"{self._path}/projects", 'POST', json=payload)
        return Project.model_validate_json(r.text)

    def get_project(self, code: str) -> Project:
        r = self._client.request(f"{self._path}/projects/{code}", 'GET')
        return Project.model_validate_json(r.text)

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
        payload: PayloadType = {
            'name': name,
            'description': description,
            'latitude': latitude,
            'longitude': longitude,
            'timezone': timezone,
            'commissioned_at': commissioned_at.isoformat() if commissioned_at is not None else None,
            'is_active': is_active,
        }
        r = self._client.request(f"{self._path}/projects/{code}", 'PUT', json=payload)
        return Project.model_validate_json(r.text)

    def delete_project(self, code: str) -> None:
        self._client.request(f"{self._path}/projects/{code}", 'DELETE')

    # --- Devices routes ---

    def list_devices(self, project: str) -> list[Device]:
        params: PayloadType = {'project': project}
        r = self._client.request(f"{self._path}/devices", 'GET', params=params)
        return _DeviceListAdapter.validate_json(r.text)

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
        channels: Optional[list[ChannelIn]] = None,
    ) -> Device:
        payload: PayloadType = {
            'project': project,
            'label': label,
            'device_type': device_type,
            'parent': parent,
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude,
        }
        payload['metadata'] = {k: v.model_dump(mode='json') for k, v in (metadata or {}).items()}  # type: ignore[assignment]
        payload['channels'] = [c.model_dump(mode='json') for c in (channels or [])]  # type: ignore[assignment]
        r = self._client.request(f"{self._path}/devices", 'POST', json=payload)
        return Device.model_validate_json(r.text)

    def get_device(self, code: str) -> Device:
        r = self._client.request(f"{self._path}/devices/{code}", 'GET')
        return Device.model_validate_json(r.text)

    def update_device(
        self,
        code: str,
        label: str,
        parent: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        metadata: Optional[dict[str, MetadataEntry]] = None,
        channels: Optional[list[ChannelIn]] = None,
    ) -> Device:
        payload: PayloadType = {
            'label': label,
            'parent': parent,
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude,
        }
        payload['metadata'] = {k: v.model_dump(mode='json') for k, v in (metadata or {}).items()}  # type: ignore[assignment]
        payload['channels'] = [c.model_dump(mode='json') for c in (channels or [])]  # type: ignore[assignment]
        r = self._client.request(f"{self._path}/devices/{code}", 'PUT', json=payload)
        return Device.model_validate_json(r.text)

    def delete_device(self, code: str) -> None:
        self._client.request(f"{self._path}/devices/{code}", 'DELETE')
