from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Optional

import requests as _requests
from pydantic import Field, TypeAdapter, field_validator

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import PayloadType
from ._util import BaseModel


class Project(BaseModel):
    class Status(BaseModel):
        last_ping: datetime
        last_ip_change: datetime
        ip_address: str
        previous_ip_address: Optional[str] = None

    code: str
    tenant: str
    name: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    commissioned_at: Optional[datetime] = None
    status: Optional[Status] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    project_number: Optional[str] = None


class DeviceChannel(BaseModel):
    field: str
    channel: str


class MetadataEntry(BaseModel):
    data_type: Literal["string", "number", "boolean", "document"]
    is_list: bool = False
    value: str | int | float | bool | None = None
    values: list[str] | list[int] | list[float] | list[bool] | None = None

    @classmethod
    def string(cls, value: str | list[str]) -> 'MetadataEntry':
        if isinstance(value, str):
            return cls(data_type='string', value=value)
        else:
            return cls(data_type='string', is_list=True, values=value)


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


# ── Device types ────────────────────────────────────────────────────────────


class DeviceTypeMetadataFieldDefinition(BaseModel):
    metadata_key: str
    description: Optional[str] = None
    data_type: Literal['string', 'number', 'boolean', 'document']
    multiple: bool = False
    unit: Optional[str] = None


class DeviceTypeChannelDefinition(BaseModel):
    field: str
    label: Optional[str] = None
    description: Optional[str] = None


class DeviceType(BaseModel):
    code: str
    label: str
    extends: Optional[str] = None
    is_abstract: bool
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    description: Optional[str] = None
    metadata_fields: list[DeviceTypeMetadataFieldDefinition]
    channels: list[DeviceTypeChannelDefinition]
    created_at: datetime
    updated_at: datetime


class ResolvedDeviceType(BaseModel):
    """Effective schema after merging this type with all ancestors via `extends`."""
    code: str
    label: str
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    description: Optional[str] = None
    metadata_fields: list[DeviceTypeMetadataFieldDefinition]
    channels: list[DeviceTypeChannelDefinition]


# ── Device groups ────────────────────────────────────────────────────────────


class DeviceGroupAnnotation(BaseModel):
    """Position of a device within the group's reference image, as normalised [0, 1] coordinates."""
    device_code: str
    x: float
    y: float

    @field_validator('x', 'y')
    @classmethod
    def _in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError('annotation coordinate must be between 0 and 1')
        return v


class DeviceGroup(BaseModel):
    code: str
    project: str
    label: str
    description: Optional[str] = None
    region: Optional[list[tuple[float, float]]] = None
    reference_document_code: Optional[str] = None
    annotations: Optional[list[DeviceGroupAnnotation]] = None
    devices: list[str]
    created_at: datetime
    updated_at: datetime


# ── Documents ────────────────────────────────────────────────────────────────


class MediaPreview(BaseModel):
    width: int
    height: int
    thumbnail_url: str


class Document(BaseModel):
    code: str
    project: str
    devices: list[str]
    file_name: str
    media_type: str
    size_bytes: int
    title: Optional[str] = None
    description: Optional[str] = None
    tags: list[str]
    preview: Optional[MediaPreview] = None
    uploaded_by: str
    created_at: datetime
    updated_at: datetime
    access_url: str


# ── Uploads ──────────────────────────────────────────────────────────────────


class UploadSession(BaseModel):
    code: str
    upload_url: str
    upload_method: str
    upload_headers: dict[str, str]
    expires_at: datetime


# ── TypeAdapters ─────────────────────────────────────────────────────────────

_ProjectListAdapter = TypeAdapter(list[Project])
_DeviceListAdapter = TypeAdapter(list[Device])
_DeviceTypeListAdapter = TypeAdapter(list[DeviceType])
_DeviceGroupListAdapter = TypeAdapter(list[DeviceGroup])
_DocumentListAdapter = TypeAdapter(list[Document])


class MercutoAssetService:
    def __init__(self, client: 'MercutoClient', path: str = '/assets') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", 'GET')
        return Healthcheck.model_validate_json(r.text)

    def ping_project(self, project: str, ip_address: str) -> None:
        payload: PayloadType = {'ip_address': ip_address}
        self._client.request(
            f"{self._path}/projects/{project}/ping", 'POST', json=payload)

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

    # --- Device types routes ---

    def list_device_types(self, limit: int = 100, offset: int = 0) -> list[DeviceType]:
        params: PayloadType = {'limit': limit, 'offset': offset}
        r = self._client.request(f"{self._path}/device-types", 'GET', params=params)
        return _DeviceTypeListAdapter.validate_json(r.text)

    def create_device_type(
        self,
        label: str,
        extends: Optional[str] = None,
        is_abstract: bool = False,
        manufacturer: Optional[str] = None,
        model_number: Optional[str] = None,
        description: Optional[str] = None,
        metadata_fields: Optional[list[DeviceTypeMetadataFieldDefinition]] = None,
        channels: Optional[list[DeviceTypeChannelDefinition]] = None,
    ) -> DeviceType:
        payload: PayloadType = {
            'label': label,
            'extends': extends,
            'is_abstract': is_abstract,
            'manufacturer': manufacturer,
            'model_number': model_number,
            'description': description,
        }
        payload['metadata_fields'] = [f.model_dump(mode='json') for f in (metadata_fields or [])]  # type: ignore[assignment]
        payload['channels'] = [c.model_dump(mode='json') for c in (channels or [])]  # type: ignore[assignment]
        r = self._client.request(f"{self._path}/device-types", 'POST', json=payload)
        return DeviceType.model_validate_json(r.text)

    def get_device_type(self, code: str, resolved: bool = False) -> DeviceType | ResolvedDeviceType:
        params: PayloadType = {'resolved': resolved}
        r = self._client.request(f"{self._path}/device-types/{code}", 'GET', params=params)
        if resolved:
            return ResolvedDeviceType.model_validate_json(r.text)
        return DeviceType.model_validate_json(r.text)

    def update_device_type(
        self,
        code: str,
        label: str,
        extends: Optional[str] = None,
        is_abstract: bool = False,
        manufacturer: Optional[str] = None,
        model_number: Optional[str] = None,
        description: Optional[str] = None,
        metadata_fields: Optional[list[DeviceTypeMetadataFieldDefinition]] = None,
        channels: Optional[list[DeviceTypeChannelDefinition]] = None,
    ) -> DeviceType:
        payload: PayloadType = {
            'label': label,
            'extends': extends,
            'is_abstract': is_abstract,
            'manufacturer': manufacturer,
            'model_number': model_number,
            'description': description,
        }
        payload['metadata_fields'] = [f.model_dump(mode='json') for f in (metadata_fields or [])]  # type: ignore[assignment]
        payload['channels'] = [c.model_dump(mode='json') for c in (channels or [])]  # type: ignore[assignment]
        r = self._client.request(f"{self._path}/device-types/{code}", 'PUT', json=payload)
        return DeviceType.model_validate_json(r.text)

    def delete_device_type(self, code: str) -> None:
        self._client.request(f"{self._path}/device-types/{code}", 'DELETE')

    # --- Device groups routes ---

    def list_device_groups(self, project: str, limit: int = 100, offset: int = 0) -> list[DeviceGroup]:
        params: PayloadType = {'project': project, 'limit': limit, 'offset': offset}
        r = self._client.request(f"{self._path}/device-groups", 'GET', params=params)
        return _DeviceGroupListAdapter.validate_json(r.text)

    def create_device_group(
        self,
        project: str,
        label: str,
        description: Optional[str] = None,
        region: Optional[list[tuple[float, float]]] = None,
        reference_document_code: Optional[str] = None,
        annotations: Optional[list[DeviceGroupAnnotation]] = None,
        devices: Optional[list[str]] = None,
    ) -> DeviceGroup:
        payload: PayloadType = {
            'project': project,
            'label': label,
            'description': description,
            'reference_document_code': reference_document_code,
            'devices': devices or [],
        }
        payload['region'] = region  # type: ignore[assignment]
        if annotations is not None:
            payload['annotations'] = [a.model_dump(mode='json') for a in annotations]  # type: ignore[assignment]
        r = self._client.request(f"{self._path}/device-groups", 'POST', json=payload)
        return DeviceGroup.model_validate_json(r.text)

    def get_device_group(self, code: str) -> DeviceGroup:
        r = self._client.request(f"{self._path}/device-groups/{code}", 'GET')
        return DeviceGroup.model_validate_json(r.text)

    def update_device_group(
        self,
        code: str,
        label: str,
        description: Optional[str] = None,
        region: Optional[list[tuple[float, float]]] = None,
        reference_document_code: Optional[str] = None,
        annotations: Optional[list[DeviceGroupAnnotation]] = None,
        devices: Optional[list[str]] = None,
    ) -> DeviceGroup:
        payload: PayloadType = {
            'label': label,
            'description': description,
            'reference_document_code': reference_document_code,
            'devices': devices or [],
        }
        payload['region'] = region  # type: ignore[assignment]
        if annotations is not None:
            payload['annotations'] = [a.model_dump(mode='json') for a in annotations]  # type: ignore[assignment]
        r = self._client.request(f"{self._path}/device-groups/{code}", 'PUT', json=payload)
        return DeviceGroup.model_validate_json(r.text)

    def delete_device_group(self, code: str) -> None:
        self._client.request(f"{self._path}/device-groups/{code}", 'DELETE')

    # --- Documents routes ---

    def list_documents(
        self,
        project: str,
        device: Optional[str] = None,
        tag: Optional[list[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        params: PayloadType = {'project': project, 'limit': limit, 'offset': offset}
        if device is not None:
            params['device'] = device
        if tag:
            params['tag'] = tag  # type: ignore[assignment]
        r = self._client.request(f"{self._path}/documents", 'GET', params=params)
        return _DocumentListAdapter.validate_json(r.text)

    def get_document(self, code: str) -> Document:
        r = self._client.request(f"{self._path}/documents/{code}", 'GET')
        return Document.model_validate_json(r.text)

    def update_document(
        self,
        code: str,
        devices: Optional[list[str]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> Document:
        payload: PayloadType = {
            'devices': devices or [],
            'title': title,
            'description': description,
            'tags': tags or [],
        }
        r = self._client.request(f"{self._path}/documents/{code}", 'PUT', json=payload)
        return Document.model_validate_json(r.text)

    def delete_document(self, code: str) -> None:
        self._client.request(f"{self._path}/documents/{code}", 'DELETE')

    # --- Uploads routes ---

    def upload_document(
        self,
        project: str,
        file_name: str,
        media_type: str,
        data: bytes,
        devices: Optional[list[str]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> Document:
        """Initiate an upload session, PUT the file bytes to the pre-signed URL, then complete."""
        payload: PayloadType = {
            'project': project,
            'file_name': file_name,
            'media_type': media_type,
            'size_bytes': len(data),
            'devices': devices or [],
            'title': title,
            'description': description,
            'tags': tags or [],
        }
        r = self._client.request(f"{self._path}/uploads", 'POST', json=payload)
        session = UploadSession.model_validate_json(r.text)

        _requests.request(
            method=session.upload_method,
            url=session.upload_url,
            headers=session.upload_headers,
            data=data,
        ).raise_for_status()

        r = self._client.request(f"{self._path}/uploads/{session.code}/complete", 'POST')
        return Document.model_validate_json(r.text)
