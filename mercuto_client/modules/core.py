from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import TypeAdapter

from . import PayloadType
from ._util import BaseModel

if TYPE_CHECKING:
    from ..client import MercutoClient


class ProjectStatus(BaseModel):
    last_ping: Optional[str]
    ip_address: Optional[str]


class Project(BaseModel):
    code: str
    name: str
    project_number: str
    active: bool
    description: str
    latitude: Optional[float]
    longitude: Optional[float]
    timezone: str
    display_timezone: Optional[str]
    tenant: str
    status: ProjectStatus
    commission_date: datetime


class WidgetConfig(BaseModel):
    type: str
    config: dict[Any, Any]
    title: Optional[str] = None
    icon: Optional[str] = None
    transparent: Optional[bool] = None


class WidgetColumn(BaseModel):
    size: Optional[str | int]
    widget: WidgetConfig


class WidgetRow(BaseModel):
    columns: list[WidgetColumn]
    title: str
    breakpoint: Optional[str]
    height: Optional[int] = None


class Dashboard(BaseModel):
    icon: Optional[str]
    name: Optional[str]
    banner_image: Optional[str]
    widgets: Optional[list[WidgetRow]]
    fullscreen: Optional[bool]


class Dashboards(BaseModel):
    dashboards: list[Dashboard]


class ItemCode(BaseModel):
    code: str


class Object(BaseModel):
    code: str
    mime_type: str
    size_bytes: int
    name: str
    event: ItemCode | None
    project: ItemCode
    access_url: str | None
    access_expires: datetime | None


class Healthcheck(BaseModel):
    ephemeral_warehouse: str
    ephemeral_document_store: str
    cache: str
    database: str


class DeviceType(BaseModel):
    code: str
    description: str
    manufacturer: str
    model_number: str


class DeviceChannel(BaseModel):
    channel: str
    field: str


class Device(BaseModel):
    code: str
    project: ItemCode
    label: str
    location_description: Optional[str]
    device_type: DeviceType
    groups: list[str]
    channels: list[DeviceChannel]


class DeviceGroup(BaseModel):
    code: str
    project: ItemCode
    label: str
    description: str
    group_label: Optional[str] = None


_ProjectListAdapter = TypeAdapter(list[Project])
_DevicesListAdapter = TypeAdapter(list[Device])
_DeviceTypeListAdapter = TypeAdapter(list[DeviceType])
_DeviceGroupListAdapter = TypeAdapter(list[DeviceGroup])


class MercutoCoreService:
    def __init__(self, client: 'MercutoClient') -> None:
        self._client = client

    def healthcheck(self) -> Healthcheck:
        r = self._client.request("/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # Projects

    def get_project(self, code: str) -> Project:
        if len(code) == 0:
            raise ValueError("Project code must not be empty")
        r = self._client.request(f'/projects/{code}', 'GET')
        return Project.model_validate_json(r.text)

    def list_projects(self) -> list[Project]:
        r = self._client.request('/projects', 'GET')
        return _ProjectListAdapter.validate_json(r.text)

    def create_project(self, name: str, project_number: str, description: str, tenant: str,
                       timezone: str,
                       latitude: Optional[float] = None,
                       longitude: Optional[float] = None) -> Project:

        payload: PayloadType = {
            'name': name,
            'project_number': project_number,
            'description': description,
            'tenant_code': tenant,
            'timezone': timezone,
        }
        if latitude is not None:
            payload['latitude'] = latitude
        if longitude is not None:
            payload['longitude'] = longitude

        r = self._client.request('/projects', 'PUT', json=payload)
        return Project.model_validate_json(r.text)

    def ping_project(self, project: str, ip_address: str) -> None:
        self._client.request(
            f'/projects/{project}/ping', 'POST', json={'ip_address': ip_address})

    def create_dashboard(self, project_code: str, dashboards: Dashboards) -> None:
        json = dashboards.model_dump()
        self._client.request(
            f'/projects/{project_code}/dashboard', 'POST', json=json)

    # DEVICES

    def list_device_types(self) -> list[DeviceType]:
        r = self._client.request('/devices/types', 'GET')
        return _DeviceTypeListAdapter.validate_json(r.text)

    def create_device_type(self, description: str, manufacturer: str, model_number: str) -> DeviceType:
        json: PayloadType = {
            'description': description,
            'manufacturer': manufacturer,
            'model_number': model_number
        }
        r = self._client.request('/devices/types', 'PUT',  json=json)
        return DeviceType.model_validate_json(r.text)

    def list_devices(self, project_code: str, limit: int, offset: int) -> list[Device]:
        params: PayloadType = {
            'project_code': project_code,
            'limit': limit,
            'offset': offset
        }
        r = self._client.request('/devices', 'GET', params=params)
        return _DevicesListAdapter.validate_json(r.text)

    def get_device(self, device_code: str) -> Device:
        r = self._client.request(f'/devices/{device_code}', 'GET')
        return Device.model_validate_json(r.text)

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
        json: PayloadType = {
            'project_code': project_code,
            'label': label,
            'device_type_code': device_type_code,
            'groups': groups,
        }
        if location_description is not None:
            json['location_description'] = location_description
        if channels is not None:
            # type: ignore[assignment]
            json['channels'] = [channel.model_dump(
                mode='json') for channel in channels]
        if latitude is not None:
            json['latitude'] = latitude
        if longitude is not None:
            json['longitude'] = longitude
        if altitude is not None:
            json['altitude'] = altitude
        r = self._client.request('/devices', 'PUT', json=json)
        return Device.model_validate_json(r.text)

    def list_device_groups(self, project: str) -> list[DeviceGroup]:
        r = self._client.request(
            '/devices/groups', 'GET', params={'project_code': project})
        return _DeviceGroupListAdapter.validate_json(r.text)
