from typing import Any, List, Literal, Optional, TypedDict


class User(TypedDict):
    code: str
    username: Optional[str]
    description: str
    tenant: str
    permission_group: str


class HiddenUserAPIKey(TypedDict):
    code: str
    description: str
    last_used: Optional[str]
    custom_policy: Optional[str]


class UserDetails(TypedDict):
    code: str
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email_address: Optional[str]
    mobile_number: Optional[str]

    api_keys: list[HiddenUserAPIKey]


class NewUserApiKey(TypedDict):
    code: str
    new_api_key: str
    description: str
    custom_policy: Optional[str]


class Tenant(TypedDict):
    code: str
    name: str
    description: str
    logo_url: Optional[str]


class AccessControlListJsonEntry(TypedDict):
    action: str
    resource: str


class AccessControlListJson(TypedDict):
    version: Literal[1]
    permissions: list[AccessControlListJsonEntry]


class PermissionGroup(TypedDict):
    tenant: str
    code: str
    label: str
    acl_policy: str


class VerifyMeResult(TypedDict):
    user: Optional[str]
    tenant: Optional[str]
    permission_group: Optional[str]
    acl_policy: str


HealthCheckMessageResult = Literal['OK', 'ERROR']


class SystemHealthcheckResult(TypedDict):
    database: HealthCheckMessageResult
    cache: HealthCheckMessageResult
    ephemeral_document_store: HealthCheckMessageResult
    ephemeral_warehouse: HealthCheckMessageResult


class AuthHealthcheckResult(TypedDict):
    status: HealthCheckMessageResult


class ProjectStatus(TypedDict):
    last_ping: Optional[str]
    last_sample: Optional[str]
    ip_address: Optional[str]


class Project(TypedDict):
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


class ProjectCode(TypedDict):
    code: str


class ItemCode(TypedDict):
    code: str


class Units(TypedDict):
    code: str
    name: str
    unit: Optional[str]


CHANNEL_CLASSIFICATION = Literal['PRIMARY', 'SECONDARY',
                                 'EVENT_METRIC', 'PRIMARY_EVENT_AGGREGATE']


class Channel(TypedDict):
    code: str
    project: ItemCode
    units: Optional[Units]
    sampling_period: Optional[str]
    classification: CHANNEL_CLASSIFICATION
    label: str
    dtype: str
    device: Optional[ItemCode]
    metric: Optional[str]
    source: Optional[ItemCode]
    aggregate: Optional[str]
    value_range_min: Optional[float]
    value_range_max: Optional[float]
    channel_multiplier: float
    channel_offset: float
    last_valid_timestamp: Optional[str]


class DeviceType(TypedDict):
    code: str
    description: str
    manufacturer: str
    model_number: str


class Device(TypedDict):
    code: str
    project: ProjectCode
    label: str
    location_description: Optional[str]
    device_type: DeviceType
    groups: List[str]


class DataSample(TypedDict):
    timestamp: str
    channel_code: str
    value: float


class WidgetConfig(TypedDict):
    type: str
    config: dict


class WidgetColumn(TypedDict):
    size: Optional[str | int]
    widget: WidgetConfig


class WidgetRow(TypedDict):
    columns: List[WidgetColumn]
    height: int
    title: str
    breakpoint: Optional[str]


class Dashboard(TypedDict):
    icon: Optional[str]
    name: Optional[str]
    banner_image: Optional[str]
    widgets: Optional[List[WidgetRow]]
    fullscreen: Optional[bool]


class Dashboards(TypedDict):
    dashboards: List[Dashboard]


class DataRequestMeta(TypedDict):
    first_timestamp: str
    last_timestamp: str


class DataRequest(TypedDict):
    code: ItemCode
    requested_at: str
    completed_at: str | None
    in_progress: bool
    presigned_url: str | None
    message: str | None
    mime_type: str
    metadata: DataRequestMeta | None


class Object(TypedDict):
    code: str
    mime_type: str
    size_bytes: int
    name: str
    event: ItemCode | None
    project: ItemCode
    access_url: str | None
    access_expires: str


class EventMetric(TypedDict):
    channel: Channel
    value: float | str | dict | list | None


class EventTag(TypedDict):
    tag: str
    value: Any | None


class Event(TypedDict):
    code: str
    project: Project
    start_time: str
    end_time: str
    objects: list[Object]
    metrics: list[EventMetric]
    tags: list[EventTag]


UserContactMethod = Literal['EMAIL', 'SMS']


class ContactGroup(TypedDict):
    project: str
    code: str
    label: str
    users: dict[str, list[UserContactMethod]]


class ScheduledReport(TypedDict):
    code: str
    project: str
    label: str
    revision: str
    schedule: Optional[str]
    contact_group: Optional[str]
    last_scheduled: Optional[str]


class ScheduledReportLog(TypedDict):
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


class DatatableColumn(TypedDict):
    code: str
    column_label: str


class DatatableOut(TypedDict):
    code: str
    name: str
    src: Optional[str]
    enabled: bool
    sampling_period: Optional[str]
    columns: list[DatatableColumn]


class Datalogger(TypedDict):
    code: str
    project: ItemCode
    name: str
    type: str
    uri: str
    datatables: list[DatatableOut]


class RainflowSource(TypedDict):
    linked_primary_channel: Channel
    sub_channels: list[Channel]


class RainflowConfiguration(TypedDict):
    project: str
    max_bins: int
    bin_size: float
    multiplier: float
    sources: list[RainflowSource]


class FatigueConnection(TypedDict):
    code: str
    label: str
    multiplier: float
    c_d: float
    m: float
    s_0: float

    bs7608_failure_probability: Optional[float]
    bs7608_detail_category: Optional[str]

    initial_date: str
    initial_damage: float
    sources: list[Channel]

    sub_channels: list[Channel]


class Condition(TypedDict):
    code: str
    source: Channel
    description: str
    upper_exclusive_bound: Optional[float]
    lower_inclusive_bound: Optional[float]
    neutral_position: float


class AlertConfiguration(TypedDict):
    code: str
    project: str
    label: str
    conditions: list[Condition]
    contact_group: Optional[ContactGroup]
    retrigger_interval: str


class AlertLogConditionEntry(TypedDict):
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


class AlertLogComment(TypedDict):
    user_code: str
    comment: str
    created_at: str


class AlertLog(TypedDict):
    code: str
    project: str
    event: Optional[str]
    acknowledged: bool
    fired_at: str
    configuration: str
    conditions: list[AlertLogConditionEntry]
    comments: list[AlertLogComment]


class ListAlertsResponseType(TypedDict):
    alerts: list[AlertLog]
    total: int


class Camera(TypedDict):
    code: str
    project: str
    label: str


class Video(TypedDict):
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


class Image(TypedDict):
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
