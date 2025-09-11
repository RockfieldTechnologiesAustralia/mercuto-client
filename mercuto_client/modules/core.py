import mimetypes
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import TypeAdapter

from . import _PayloadType
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
    contact_group: Optional[ContactGroup]
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
    aggregate: Literal["max", "greatest", "min", "median", "abs-max", "mean", "rms", "peak-to-peak", "daf"]
    enabled: bool = True
    options: Optional[dict[str, Any]] = None


class Camera(BaseModel):
    code: str
    project: str
    label: str


class Video(BaseModel):
    code: str
    project: str
    camera: str | None
    start_time: str
    end_time: str
    mime_type: str
    size_bytes: int
    name: str
    event: str | None
    access_url: str | None
    access_expires: str


class Image(BaseModel):
    code: str
    project: str
    camera: str | None
    timestamp: str | None
    mime_type: str
    size_bytes: int
    name: str
    event: str | None
    access_url: str | None
    access_expires: str


class ScheduledReport(BaseModel):
    code: str
    project: str
    label: str
    revision: str
    schedule: Optional[str]
    contact_group: Optional[str]
    last_scheduled: Optional[str]


class ScheduledReportLog(BaseModel):
    code: str
    report: str
    scheduled_start: Optional[str]
    actual_start: str
    actual_finish: Optional[str]
    status: Literal['IN_PROGRESS', 'COMPLETED', 'FAILED']
    message: Optional[str]
    access_url: Optional[str]
    mime_type: Optional[str]
    filename: Optional[str]


class ReportSourceCodeRevision(BaseModel):
    code: str
    revision_date: datetime
    description: str
    source_code_url: str


_ProjectListAdapter = TypeAdapter(list[Project])
_EventsListAdapter = TypeAdapter(list[Event])
_DevicesListAdapter = TypeAdapter(list[Device])
_DeviceTypeListAdapter = TypeAdapter(list[DeviceType])
_ImageListAdapter = TypeAdapter(list[Image])
_VideoListAdapter = TypeAdapter(list[Video])
_CameraListAdapter = TypeAdapter(list[Camera])
_ContactGroupListAdapter = TypeAdapter(list[ContactGroup])
_ScheduledReportListAdapter = TypeAdapter(list[ScheduledReport])
_ScheduledReportLogListAdapter = TypeAdapter(list[ScheduledReportLog])


class MercutoCoreService:
    def __init__(self, client: 'MercutoClient') -> None:
        self._client = client

    def healthcheck(self) -> Healthcheck:
        r = self._client._http_request("/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # Projects

    def get_project(self, code: str) -> Project:
        if len(code) == 0:
            raise ValueError("Project code must not be empty")
        r = self._client._http_request(f'/projects/{code}', 'GET')
        return Project.model_validate_json(r.text)

    def list_projects(self) -> list[Project]:
        r = self._client._http_request('/projects', 'GET')
        return _ProjectListAdapter.validate_json(r.text)

    def create_project(self, name: str, project_number: str, description: str, tenant: str,
                       timezone: str,
                       latitude: Optional[float] = None,
                       longitude: Optional[float] = None) -> Project:

        payload: _PayloadType = {
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

        r = self._client._http_request('/projects', 'PUT', json=payload)
        return Project.model_validate_json(r.text)

    def ping_project(self, project: str, ip_address: str) -> None:
        self._client._http_request(f'/projects/{project}/ping', 'POST', json={'ip_address': ip_address})

    def create_dashboard(self, project_code: str, dashboards: Dashboards) -> None:
        json = dashboards.model_dump()
        self._client._http_request(f'/projects/{project_code}/dashboard', 'POST', json=json)

    def set_project_event_detection(self, project: str, datatables: list[str]) -> ProjectEventDetection:
        if len(datatables) == 0:
            raise ValueError('At least one datatable must be provided to enable event detection')

        params: _PayloadType = {
            "enabled": True,
            "datatables": datatables
        }
        r = self._client._http_request(f'/projects/{project}/event-detection', 'POST', json=params)
        return ProjectEventDetection.model_validate_json(r.text)

    # EVENTS

    def create_event(self, project: str, start_time: datetime, end_time: datetime) -> Event:
        if start_time.tzinfo is None or end_time.tzinfo is None:
            raise ValueError("Timestamp must be timezone aware")

        json: _PayloadType = {
            'project': project,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
        }
        r = self._client._http_request('/events', 'PUT', json=json)
        return Event.model_validate_json(r.text)

    def list_events(self, project: str) -> list[Event]:
        params: _PayloadType = {'project_code': project}
        r = self._client._http_request('/events', 'GET', params=params)
        return _EventsListAdapter.validate_json(r.text)

    def get_event(self, event: str) -> Event:
        r = self._client._http_request(f'/events/{event}', 'GET')
        return Event.model_validate_json(r.text)

    def delete_event(self, event: str) -> None:
        self._client._http_request(f'/events/{event}', 'DELETE')

    def get_nearest_event(
        self,
        project_code: str,
        to: datetime,
        maximum_delta: timedelta | None = None,
    ) -> Event:
        params: _PayloadType = {
            'project_code': project_code,
            'to': to.isoformat(),
        }
        if maximum_delta is not None:
            params['maximum_delta'] = serialise_timedelta(maximum_delta)

        r = self._client._http_request('/events/nearest', 'GET', params=params)
        return Event.model_validate_json(r.text)

    def set_event_aggregates(self, project: str, aggregates: list[EventAggregate]) -> None:
        self._client._http_request('/aggregates', 'PUT',
                                   json=[agg.model_dump(mode='json') for agg in aggregates],  # type: ignore
                                   params={'project_code': project})

    # ALERTS

    def get_condition(self, code: str) -> Condition:
        r = self._client._http_request(f'/alerts/conditions/{code}', 'GET')
        return Condition.model_validate_json(r.text)

    def create_condition(self, source: str, description: str, *,
                         lower_bound: Optional[float] = None,
                         upper_bound: Optional[float] = None,
                         neutral_position: float = 0) -> Condition:
        json: _PayloadType = {
            'source_channel_code': source,
            'description': description,
            'neutral_position': neutral_position
        }
        if lower_bound is not None:
            json['lower_inclusive_bound'] = lower_bound
        if upper_bound is not None:
            json['upper_exclusive_bound'] = upper_bound
        r = self._client._http_request('/alerts/conditions', 'PUT',  json=json)
        return Condition.model_validate_json(r.text)

    def create_alert_configuration(self, label: str,
                                   conditions: list[str],
                                   contact_group: Optional[str] = None) -> AlertConfiguration:
        json: _PayloadType = {
            'label': label,
            'conditions': conditions,

        }
        if contact_group is not None:
            json['contact_group'] = contact_group
        r = self._client._http_request('/alerts/configurations', 'PUT', json=json)
        return AlertConfiguration.model_validate_json(r.text)

    def get_alert_configuration(self, code: str) -> AlertConfiguration:
        r = self._client._http_request(f'/alerts/configurations/{code}', 'GET')
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
        params: _PayloadType = {
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
            params['start_time'] = start_time.isoformat() if isinstance(start_time, datetime) else start_time
        if end_time is not None:
            params['end_time'] = end_time.isoformat() if isinstance(end_time, datetime) else end_time

        r = self._client._http_request('/alerts/logs', 'GET', params=params)
        return AlertSummary.model_validate_json(r.text)

    # DEVICES

    def list_device_types(self) -> list[DeviceType]:
        r = self._client._http_request('/devices/types', 'GET')
        return _DeviceTypeListAdapter.validate_json(r.text)

    def create_device_type(self, description: str, manufacturer: str, model_number: str) -> DeviceType:
        json: _PayloadType = {
            'description': description,
            'manufacturer': manufacturer,
            'model_number': model_number
        }
        r = self._client._http_request('/devices/types', 'PUT',  json=json)
        return DeviceType.model_validate_json(r.text)

    def list_devices(self, project_code: str, limit: int, offset: int) -> list[Device]:
        params: _PayloadType = {
            'project_code': project_code,
            'limit': limit,
            'offset': offset
        }
        r = self._client._http_request('/devices', 'GET', params=params)
        return _DevicesListAdapter.validate_json(r.text)

    def get_device(self, device_code: str) -> Device:
        r = self._client._http_request(f'/devices/{device_code}', 'GET')
        return Device.model_validate_json(r.text)

    def create_device(self,
                      project_code: str,
                      label: str,
                      device_type_code: str,
                      groups: list[str],
                      location_description: Optional[str] = None,
                      channels: Optional[list[DeviceChannel]] = None) -> Device:
        json: _PayloadType = {
            'project_code': project_code,
            'label': label,
            'device_type_code': device_type_code,
            'groups': groups,
        }
        if location_description is not None:
            json['location_description'] = location_description
        if channels is not None:
            json['channels'] = [channel.model_dump(mode='json') for channel in channels]  # type: ignore[assignment]
        r = self._client._http_request('/devices', 'PUT', json=json)
        return Device.model_validate_json(r.text)

    # MEDIA

    def list_cameras(self, project: str) -> list[Camera]:
        params: _PayloadType = {}
        params['project_code'] = project
        r = self._client._http_request('/media/cameras', 'GET', params=params)
        return _CameraListAdapter.validate_json(r.text)

    def list_videos(self, project: Optional[str] = None, event: Optional[str] = None, camera: Optional[str] = None) -> list[Video]:
        params: _PayloadType = {}
        if project is not None:
            params['project'] = project
        if event is not None:
            params['event'] = event
        if camera is not None:
            params['camera'] = camera
        r = self._client._http_request('/media/videos', 'GET', params=params)
        return _VideoListAdapter.validate_json(r.text)

    def get_video(self, code: str) -> Video:
        r = self._client._http_request(f'/media/videos/{code}', 'GET')
        return Video.model_validate_json(r.text)

    def list_images(self, project: Optional[str] = None, event: Optional[str] = None, camera: Optional[str] = None) -> list[Image]:
        params = {}
        if project is not None:
            params['project'] = project
        if event is not None:
            params['event'] = event
        if camera is not None:
            params['camera'] = camera
        r = self._client._http_request('/media/images', 'GET', params=params)
        return _ImageListAdapter.validate_json(r.text)

    def get_image(self, code: str) -> Image:
        r = self._client._http_request(f'/media/images/{code}', 'GET')
        return Image.model_validate_json(r.text)

    def upload_image(self, project: str, file: str, event: Optional[str] = None,
                     camera: Optional[str] = None, timestamp: Optional[datetime] = None,
                     filename: Optional[str] = None) -> Image:
        if timestamp is not None and timestamp.tzinfo is None:
            raise ValueError("Timestamp must be timezone aware")

        mimetype, _ = mimetypes.guess_type(file, strict=False)
        if mimetype is None or not mimetype.startswith('image/'):
            raise ValueError(f"File {file} is not an image")

        if os.stat(file).st_size > 5_000_000:
            raise ValueError(f"File {file} is too large")

        if filename is None:
            filename = os.path.basename(file)

        params: _PayloadType = {}
        params['project'] = project
        if event is not None:
            params['event'] = event
        if camera is not None:
            params['camera'] = camera
        if timestamp is not None:
            params['timestamp'] = timestamp.isoformat()

        with open(file, 'rb') as f:
            r = self._client._http_request('/media/images', 'PUT',
                                           params=params,
                                           files={
                                               'file': (filename, f, mimetype)
                                           })
        return Image.model_validate_json(r.text)

    def upload_video(self, project: str, file: str,
                     start_time: datetime, end_time: datetime,
                     event: Optional[str] = None,
                     filename: Optional[str] = None) -> Video:
        if start_time.tzinfo is None:
            raise ValueError("Timestamp must be timezone aware")
        if end_time.tzinfo is None:
            raise ValueError("Timestamp must be timezone aware")

        mimetype, _ = mimetypes.guess_type(file, strict=False)
        if mimetype is None or not mimetype.startswith('video/'):
            raise ValueError(f"File {file} is not a video")

        if os.stat(file).st_size > 5_000_000:
            raise ValueError(f"File {file} is too large")

        if filename is None:
            filename = os.path.basename(file)

        params: _PayloadType = {}
        params['project'] = project
        params['start_time'] = start_time.isoformat()
        params['end_time'] = end_time.isoformat()
        if event is not None:
            params['event'] = event

        with open(file, 'rb') as f:
            r = self._client._http_request('/media/videos', 'PUT',
                                           params=params,
                                           files={
                                               'file': (filename, f, mimetype)
                                           })
        return Video.model_validate_json(r.text)

    # Contacts

    def list_contact_groups(self, project: Optional[str] = None) -> list[ContactGroup]:
        params: _PayloadType = {}
        if project is not None:
            params['project'] = project
        r = self._client._http_request('/notifications/contact_groups', 'GET', params=params)
        return _ContactGroupListAdapter.validate_json(r.text)

    def get_contact_group(self, code: str) -> ContactGroup:
        r = self._client._http_request(f'/notifications/contact_groups/{code}', 'GET')
        return ContactGroup.model_validate_json(r.text)

    def create_contact_group(self, project: str, label: str, users: dict[str, list[UserContactMethod]]) -> ContactGroup:
        r = self._client._http_request('/notifications/contact_groups', 'PUT',
                                       json={
                                           'project': project,
                                           'label': label,
                                           'users': users
                                       })
        return ContactGroup.model_validate_json(r.text)

    # Reports
    def list_reports(self, project: Optional[str] = None) -> list['ScheduledReport']:
        params: _PayloadType = {}
        if project is not None:
            params['project'] = project
        r = self._client._http_request('/reports/scheduled', 'GET', params=params)
        return _ScheduledReportListAdapter.validate_json(r.text)

    def create_report(self, project: str, label: str, schedule: str, revision: str,
                      api_key: Optional[str] = None, contact_group: Optional[str] = None) -> ScheduledReport:
        json: _PayloadType = {
            'project': project,
            'label': label,
            'schedule': schedule,
            'revision': revision,
            'execution_role_api_key': api_key,
            'contact_group': contact_group
        }
        r = self._client._http_request('/reports/scheduled', 'PUT', json=json)
        return ScheduledReport.model_validate_json(r.text)

    def generate_report(self, report: str, timestamp: datetime, mark_as_scheduled: bool = False) -> ScheduledReportLog:
        r = self._client._http_request(f'/reports/scheduled/{report}/generate', 'PUT', json={
            'timestamp': timestamp.isoformat(),
            'mark_as_scheduled': mark_as_scheduled
        })
        return ScheduledReportLog.model_validate_json(r.text)

    def list_report_logs(self, report: str, project: Optional[str] = None) -> list[ScheduledReportLog]:
        params: _PayloadType = {}
        if project is not None:
            params['project'] = project
        r = self._client._http_request(f'/reports/scheduled/{report}/logs', 'GET', params=params)
        return _ScheduledReportLogListAdapter.validate_json(r.text)

    def get_report_log(self, report: str, log: str) -> ScheduledReportLog:
        r = self._client._http_request(f'/reports/scheduled/{report}/logs/{log}', 'GET')
        return ScheduledReportLog.model_validate_json(r.text)

    def create_report_revision(self, project: str, revision_date: datetime, description: str, source_code_data_url: str) -> ReportSourceCodeRevision:
        json = {
            'revision_date': revision_date.isoformat(),
            'description': description,
            'source_code_data_url': source_code_data_url,
        }
        r = self._client._http_request('/reports/revisions', 'PUT', json=json, params={'project': project})
        return ReportSourceCodeRevision.model_validate_json(r.text)
