from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Optional

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


UserContactMethod = Literal['EMAIL', 'SMS']


class ContactGroup(BaseModel):
    project: str
    code: str
    label: str
    users: dict[str, list[UserContactMethod]]


class Condition(BaseModel):
    code: str
    source: str
    description: str
    upper_exclusive_bound: Optional[float]
    lower_inclusive_bound: Optional[float]
    neutral_position: float


class AlertConfiguration(BaseModel):
    code: str
    project: str
    label: str
    conditions: list[Condition]
    contact_group: Optional[str]
    retrigger_interval: Optional[datetime]


class AlertLogConditionEntry(BaseModel):
    condition: Condition
    start_value: float
    start_time: str
    start_percentile: float

    peak_value: float
    peak_time: str
    peak_percentile: float

    end_value: float
    end_time: str
    end_percentile: float


class AlertLogComment(BaseModel):
    user_code: str
    comment: str
    created_at: str


class AlertLog(BaseModel):
    code: str
    project: str
    event: Optional[str]
    acknowledged: bool
    fired_at: str
    configuration: str
    conditions: list[AlertLogConditionEntry]
    comments: list[AlertLogComment]


class AlertSummary(BaseModel):
    alerts: list[AlertLog]
    total: int


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


class EventAggregate(BaseModel):
    aggregate: Literal["max", "greatest", "min", "median",
                       "abs-max", "mean", "rms", "peak-to-peak", "daf"]
    enabled: bool = True
    options: Optional[dict[str, Any]] = None


_ProjectListAdapter = TypeAdapter(list[Project])
_DevicesListAdapter = TypeAdapter(list[Device])
_DeviceTypeListAdapter = TypeAdapter(list[DeviceType])
_DeviceGroupListAdapter = TypeAdapter(list[DeviceGroup])
_ConditionListAdapter = TypeAdapter(list[Condition])


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

    def set_event_aggregates(self, project: str, aggregates: list[EventAggregate]) -> None:
        self._client.request('/aggregates', 'PUT',
                             json=[agg.model_dump(mode='json') for agg in aggregates],  # type: ignore
                             params={'project_code': project})

    # ALERTS
    def list_conditions(self, project: str, limit: int = 100, offset: int = 0) -> list[Condition]:
        params: PayloadType = {
            'project': project,
            'limit': limit,
            'offset': offset
        }
        r = self._client.request('/alerts/conditions', 'GET', params=params)
        return _ConditionListAdapter.validate_json(r.text)

    def get_condition(self, code: str) -> Condition:
        r = self._client.request(f'/alerts/conditions/{code}', 'GET')
        return Condition.model_validate_json(r.text)

    def create_condition(self, source: str, description: str, *,
                         lower_bound: Optional[float] = None,
                         upper_bound: Optional[float] = None,
                         neutral_position: float = 0) -> Condition:
        json: PayloadType = {
            'source_channel_code': source,
            'description': description,
            'neutral_position': neutral_position
        }
        if lower_bound is not None:
            json['lower_inclusive_bound'] = lower_bound
        if upper_bound is not None:
            json['upper_exclusive_bound'] = upper_bound
        r = self._client.request('/alerts/conditions', 'PUT',  json=json)
        return Condition.model_validate_json(r.text)

    def create_alert_configuration(self, label: str,
                                   conditions: list[str],
                                   contact_group: Optional[str] = None) -> AlertConfiguration:
        json: PayloadType = {
            'label': label,
            'conditions': conditions,

        }
        if contact_group is not None:
            json['contact_group'] = contact_group
        r = self._client.request(
            '/alerts/configurations', 'PUT', json=json)
        return AlertConfiguration.model_validate_json(r.text)

    def get_alert_configuration(self, code: str) -> AlertConfiguration:
        r = self._client.request(f'/alerts/configurations/{code}', 'GET')
        return AlertConfiguration.model_validate_json(r.text)

    def list_alert_logs(
            self,
            project: str | None = None,
            configuration: str | None = None,
            channels: list[str] | None = None,
            start_time: datetime | str | None = None,
            end_time: datetime | str | None = None,
            limit: int = 10,
            offset: int = 0,
            latest_only: bool = False,
    ) -> AlertSummary:
        params: PayloadType = {
            'limit': limit,
            'offset': offset,
            'latest_only': latest_only,
        }

        if project is not None:
            params['project'] = project
        if configuration is not None:
            params['configuration_code'] = configuration
        if channels is not None:
            params['channels'] = channels
        if start_time is not None:
            params['start_time'] = start_time.isoformat() if isinstance(
                start_time, datetime) else start_time
        if end_time is not None:
            params['end_time'] = end_time.isoformat() if isinstance(
                end_time, datetime) else end_time

        r = self._client.request('/alerts/logs', 'GET', params=params)
        return AlertSummary.model_validate_json(r.text)

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
            json['channels'] = [channel.model_dump(mode='json') for channel in channels]  # type: ignore[assignment]
        if latitude is not None:
            json['latitude'] = latitude
        if longitude is not None:
            json['longitude'] = longitude
        if altitude is not None:
            json['altitude'] = altitude
        r = self._client.request('/devices', 'PUT', json=json)
        return Device.model_validate_json(r.text)

    def list_device_groups(self, project: str) -> list[DeviceGroup]:
        r = self._client.request('/devices/groups', 'GET', params={'project_code': project})
        return _DeviceGroupListAdapter.validate_json(r.text)
