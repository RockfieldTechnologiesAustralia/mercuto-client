from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Optional

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
    project_number: Optional[str] = None


class DeviceChannel(BaseModel):
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
                raise ValueError(
                    "`values` must be null when `is_list` is false")
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
    channels: list[DeviceChannel] = []
    children: list[str] = []
    created_at: datetime
    updated_at: datetime


class Healthcheck(BaseModel):
    status: str


class DashboardWidget(BaseModel):
    type: str
    title: Optional[str] = None
    icon: Optional[str] = None
    transparent: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class DashboardColumn(BaseModel):
    size: str | int | None = None
    widget: DashboardWidget


class DashboardRow(BaseModel):
    title: Optional[str] = None
    height: Optional[int] = None
    breakpoint: Literal['xs', 'sm', 'md', 'lg', 'xl', 'xxl'] = 'md'
    columns: list[DashboardColumn] = []


class DashboardDefinition(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    banner_image: Optional[str] = None
    fullscreen: bool = False
    widgets: list[DashboardRow] = []


class ChannelStyle(BaseModel):
    colour: Optional[str] = None
    mode: Optional[str] = None


class StylesConfig(BaseModel):
    channel_styles: dict[str, ChannelStyle] = Field(default_factory=dict)


class DeviceTypeMapIcon(BaseModel):
    device_type_code: str
    icon: str


class MapConfig(BaseModel):
    default_style: Optional[str] = 'satellite'
    device_type_icons: Optional[list[DeviceTypeMapIcon]] = None
    visible_fields: Optional[list[str]] = None
    cluster_enabled: Optional[bool] = True
    show_labels: Optional[bool] = True
    show_sample_values: Optional[bool] = True
    sample_text_layout: Optional[Literal['vertical', 'horizontal']] = None
    default_zoom: Optional[float] = None
    default_center_lat: Optional[float] = None
    default_center_lng: Optional[float] = None
    decimal_precision: Optional[int] = Field(default=1, ge=0, le=6)
    cluster_max_zoom: Optional[int] = Field(default=None, ge=1, le=24)
    cluster_radius: Optional[int] = Field(default=None, ge=1)
    use_device_group_regions: Optional[bool] = False


class FeaturesConfig(BaseModel):
    events: bool = False
    fatigue: bool = False
    statistics: bool = False
    map: bool = False
    reports: bool = False
    alarms: bool = False
    media: bool = False
    beta: bool = False


class PreferencesConfig(BaseModel):
    default_event_channels: list[str] = Field(default_factory=list)


class Display(BaseModel):
    dashboards: list[DashboardDefinition]
    styles: StylesConfig
    map: MapConfig
    features: FeaturesConfig
    preferences: PreferencesConfig
    updated_at: datetime


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
        self._client.request(
            f"{self._path}/projects/{code}/ping", 'POST', json=payload)

    # --- Display routes ---

    def get_display(self, code: str) -> Display:
        r = self._client.request(
            f"{self._path}/projects/{code}/display", 'GET')
        return Display.model_validate_json(r.text)

    def put_display_dashboards(self, code: str, value: list[DashboardDefinition]) -> Display:
        payload: PayloadType = {'section': 'dashboards'}
        payload['value'] = [v.model_dump(mode='json') for v in value]  # type: ignore[assignment]
        r = self._client.request(
            f"{self._path}/projects/{code}/display", 'PUT', json=payload)
        return Display.model_validate_json(r.text)

    def put_display_styles(self, code: str, value: StylesConfig) -> Display:
        payload: PayloadType = {
            'section': 'styles',
            # type: ignore[assignment]
            'value': value.model_dump(mode='json'),
        }
        r = self._client.request(
            f"{self._path}/projects/{code}/display", 'PUT', json=payload)
        return Display.model_validate_json(r.text)

    def put_display_map(self, code: str, value: MapConfig) -> Display:
        payload: PayloadType = {
            'section': 'map',
            # type: ignore[assignment]
            'value': value.model_dump(mode='json'),
        }
        r = self._client.request(
            f"{self._path}/projects/{code}/display", 'PUT', json=payload)
        return Display.model_validate_json(r.text)

    def put_display_features(self, code: str, value: FeaturesConfig) -> Display:
        payload: PayloadType = {
            'section': 'features',
            # type: ignore[assignment]
            'value': value.model_dump(mode='json'),
        }
        r = self._client.request(
            f"{self._path}/projects/{code}/display", 'PUT', json=payload)
        return Display.model_validate_json(r.text)

    def put_display_preferences(self, code: str, value: PreferencesConfig) -> Display:
        payload: PayloadType = {
            'section': 'preferences',
            # type: ignore[assignment]
            'value': value.model_dump(mode='json'),
        }
        r = self._client.request(
            f"{self._path}/projects/{code}/display", 'PUT', json=payload)
        return Display.model_validate_json(r.text)

    # --- Projects routes ---

    def list_projects(self, limit: int = 100, offset: int = 0) -> list[Project]:
        params: PayloadType = {
            'limit': limit,
            'offset': offset,
        }
        r = self._client.request(f"{self._path}/projects", 'GET', params=params)
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
        project_number: Optional[str] = None,
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
        r = self._client.request(
            f"{self._path}/projects", 'POST', json=payload)
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
        r = self._client.request(
            f"{self._path}/projects/{code}", 'PUT', json=payload)
        return Project.model_validate_json(r.text)

    def delete_project(self, code: str) -> None:
        self._client.request(f"{self._path}/projects/{code}", 'DELETE')

    # --- Devices routes ---

    def list_devices(self, project: str, limit: int = 100, offset: int = 0) -> list[Device]:
        params: PayloadType = {
            'project': project,
            'limit': limit,
            'offset': offset,
        }
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
        channels: Optional[list[DeviceChannel]] = None,
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
        channels: Optional[list[DeviceChannel]] = None,
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
        r = self._client.request(
            f"{self._path}/devices/{code}", 'PUT', json=payload)
        return Device.model_validate_json(r.text)

    def delete_device(self, code: str) -> None:
        self._client.request(f"{self._path}/devices/{code}", 'DELETE')
