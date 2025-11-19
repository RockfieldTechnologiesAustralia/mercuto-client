from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import TypeAdapter

from . import PayloadType
from ._util import BaseModel, serialise_timedelta

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


class WidgetColumn(BaseModel):
    size: Optional[str | int]
    widget: WidgetConfig


class WidgetRow(BaseModel):
    columns: list[WidgetColumn]
    height: int
    title: str
    breakpoint: Optional[str]


class Dashboard(BaseModel):
    icon: Optional[str]
    name: Optional[str]
    banner_image: Optional[str]
    widgets: Optional[list[WidgetRow]]
    fullscreen: Optional[bool]


class Dashboards(BaseModel):
    dashboards: list[Dashboard]


class ProjectEventDetection(BaseModel):
    enabled: bool
    datatables: list[str]
    max_duration: timedelta
    max_files: int
    maximise: bool
    overlap_period: timedelta
    split_interval_cron: Optional[str]


class ItemCode(BaseModel):
    code: str


class EventTag(BaseModel):
    tag: str
    value: Any | None


class Object(BaseModel):
    code: str
    mime_type: str
    size_bytes: int
    name: str
    event: ItemCode | None
    project: ItemCode
    access_url: str | None
    access_expires: datetime | None


class Event(BaseModel):
    code: str
    project: ItemCode
    start_time: datetime
    end_time: datetime
    objects: list[Object]
    tags: list[EventTag]


class EventStatisticsOut(BaseModel):
    n_events_last_week: int
    n_events_last_month: int
    n_events_last_year: int
    n_events_all_time: int
    n_events_in_range: int
    last_event: Optional[Event] = None


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


class EventAggregate(BaseModel):
    aggregate: Literal["max", "greatest", "min", "median",
                       "abs-max", "mean", "rms", "peak-to-peak", "daf"]
    enabled: bool = True
    options: Optional[dict[str, Any]] = None


_ProjectListAdapter = TypeAdapter(list[Project])
_EventsListAdapter = TypeAdapter(list[Event])
_DevicesListAdapter = TypeAdapter(list[Device])
_DeviceTypeListAdapter = TypeAdapter(list[DeviceType])


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

    def set_project_event_detection(self, project: str, datatables: list[str]) -> ProjectEventDetection:
        if len(datatables) == 0:
            raise ValueError(
                'At least one datatable must be provided to enable event detection')

        params: PayloadType = {
            "enabled": True,
            "datatables": datatables
        }
        r = self._client.request(
            f'/projects/{project}/event-detection', 'POST', json=params)
        return ProjectEventDetection.model_validate_json(r.text)

    # EVENTS

    def create_event(self, project: str, start_time: datetime, end_time: datetime) -> Event:
        if start_time.tzinfo is None or end_time.tzinfo is None:
            raise ValueError("Timestamp must be timezone aware")

        json: PayloadType = {
            'project': project,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
        }
        r = self._client.request('/events', 'PUT', json=json)
        return Event.model_validate_json(r.text)

    def list_events(self, project: str,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: Optional[int] = None, offset: Optional[int] = 0,
                    ascending: bool = True) -> list[Event]:
        """
        Lists events for a project, optionally filtered by time range.
        :param project: Project code to list events for.
        :param start_time: Optional start time to filter events from.
        :param end_time: Optional end time to filter events to.
        :param limit: Optional maximum number of events to return. Default is set by API (usually 10).
        :param offset: Optional offset for pagination.
        :param ascending: Whether to sort events in ascending order by start time.
        :return: List of Event objects.
        """
        params: PayloadType = {'project_code': project, 'ascending': ascending}
        if start_time is not None:
            params['start_time'] = start_time.isoformat()
        if end_time is not None:
            params['end_time'] = end_time.isoformat()
        if limit is not None:
            params['limit'] = limit
        if offset is not None:
            params['offset'] = offset
        r = self._client.request('/events', 'GET', params=params)
        return _EventsListAdapter.validate_json(r.text)

    def get_event(self, event: str) -> Event:
        r = self._client.request(f'/events/{event}', 'GET')
        return Event.model_validate_json(r.text)

    def delete_event(self, event: str) -> None:
        self._client.request(f'/events/{event}', 'DELETE')

    def get_nearest_event(
        self,
        project_code: str,
        to: datetime,
        maximum_delta: timedelta | None = None,
    ) -> Event:
        params: PayloadType = {
            'project_code': project_code,
            'to': to.isoformat(),
        }
        if maximum_delta is not None:
            params['maximum_delta'] = serialise_timedelta(maximum_delta)

        r = self._client.request('/events/nearest', 'GET', params=params)
        return Event.model_validate_json(r.text)

    def get_event_statistics(
        self,
        project_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> EventStatisticsOut:
        params: PayloadType = {
            'project_code': project_code,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
        }

        r = self._client.request('/events/statistics', 'GET', params=params)
        return EventStatisticsOut.model_validate_json(r.text)

    def set_event_aggregates(self, project: str, aggregates: list[EventAggregate]) -> None:
        self._client.request('/aggregates', 'PUT',
                             json=[agg.model_dump(mode='json') for agg in aggregates],  # type: ignore
                             params={'project_code': project})

    # ALERTS

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
                      channels: Optional[list[DeviceChannel]] = None) -> Device:
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
        r = self._client.request('/devices', 'PUT', json=json)
        return Device.model_validate_json(r.text)
