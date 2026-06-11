from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import PayloadType
from ._util import BaseModel

# ── Events ───────────────────────────────────────────────
EventDetectorType = Literal['cron', 'generic']


class CronDetectorConfig(BaseModel):
    cron_expression: str
    detector_type: Literal['cron'] = 'cron'


class GenericDetectorConfig(BaseModel):
    max_gap: timedelta = timedelta(seconds=1)
    max_duration: timedelta = timedelta(hours=1)
    max_files: int = -1
    maximise: bool = True
    detector_type: Literal['generic'] = 'generic'


class Tag(BaseModel):
    tag_name: str
    tag_value: str | list[Any] | dict[str, Any] | int | float | bool | None


class Vehicle(BaseModel):
    vehicle_index: int
    classification: Optional[str] = None
    velocity_ms: Optional[float] = None
    axle_positions: list[float]
    axle_masses_kg: list[float]
    gross_vehicle_mass_kg: Optional[float] = None


class Artifact(BaseModel):
    id: int
    category: str
    filename: str
    download_url: str
    mime_type: str
    size_bytes: int
    vehicle_id: Optional[int] = None


class Event(BaseModel):
    project: str
    code: str
    start_time: datetime
    end_time: datetime
    tags: list[Tag]
    vehicles: list[Vehicle]
    artifacts: list[Artifact]


class EventStatus(BaseModel):
    service: str
    status: Literal['completed', 'failed']
    message: str | None
    updated_at: datetime


# ── Detectors ────────────────────────────────────────────


class DetectorSettings(BaseModel):
    id: int
    project: str
    enabled: bool
    config: CronDetectorConfig | GenericDetectorConfig
    datatables: list[str]


# ── Processing ───────────────────────────────────────────


class BridgeSpanType(Enum):
    BENDING_STRAINS = 'bending-strains'
    BEARING_STRAINS_START_SIDE = 'bearing-strains-start-side'
    BEARING_STRAINS_END_SIDE = 'bearing-strains-end-side'
    BEARING_STRAINS_BOTH_SIDES = 'bearing-strains-both-sides'


class GirderGroupConfig(BaseModel):
    channels: dict[str, float]


class VelocityEstimationConfig(BaseModel):
    source_channel_a: str
    source_channel_b: str
    sensor_spacing_m: float
    window_start_threshold: Optional[float] = None
    window_start_offset_seconds: Optional[float] = None
    window_end_offset_seconds: Optional[float] = None
    generate_plots: bool = True
    metric_channel: Optional[str] = None


class AxleDetectionConfig(BaseModel):
    span_length_m: float
    skew_deg: float = 0.0
    group_1: Optional[GirderGroupConfig] = None
    group_2: Optional[GirderGroupConfig] = None


class MassEstimationConfig(BaseModel):
    span_length_m: float
    strain_group: GirderGroupConfig
    span_type: BridgeSpanType = BridgeSpanType.BENDING_STRAINS
    skew_deg: float = 0.0
    kg_per_strain: float = 1.0
    quasi_static_cutoff_hz: Optional[float] = None
    remove_baseline: bool = True
    group_load_sharing_ratio: Optional[float] = None
    generate_debug_plots: bool = False
    metric_channel: Optional[str] = None


class VehicleBWimConfig(BaseModel):
    axle_detection: AxleDetectionConfig
    mass_estimation: MassEstimationConfig


class LoadDistributionConfig(BaseModel):
    group: GirderGroupConfig
    metric_channel: Optional[str] = None


class AggregationConfig(BaseModel):
    aggregate: str
    options: Optional[dict[str, Any]] = None


class DynamicAmplificationConfig(BaseModel):
    minimum_frequency: float = 0.5
    maximum_frequency: float = 8.0
    filter_order: int = 5
    sweep_start_frequency: float = 0.1
    sweep_end_frequency: float = 10.0
    sweep_step_frequency: float = 0.1
    minimum_amplitude: float = 10.0


class CalibrationAxle(BaseModel):
    position_m: float
    mass_kg: float


class CalibrationVehicle(BaseModel):
    event_code: str
    axles: list[CalibrationAxle]
    known_velocity_kmh: float


class CalibrationMetadata(BaseModel):
    calibrated_at: datetime
    vehicles: list[CalibrationVehicle]
    kg_per_strain: float
    report_url: str


class ProcessingConfigBodyIn(BaseModel):
    aggregation: Optional[list[AggregationConfig]] = None
    velocity_estimation: Optional[VelocityEstimationConfig] = None
    dynamic_amplification: Optional[DynamicAmplificationConfig] = None
    vehicle_bwim: Optional[VehicleBWimConfig] = None
    load_distribution: Optional[LoadDistributionConfig] = None


class ProcessingConfigBody(BaseModel):
    aggregation: Optional[list[AggregationConfig]] = None
    velocity_estimation: Optional[VelocityEstimationConfig] = None
    dynamic_amplification: Optional[DynamicAmplificationConfig] = None
    vehicle_bwim: Optional[VehicleBWimConfig] = None
    load_distribution: Optional[LoadDistributionConfig] = None
    calibration: Optional[CalibrationMetadata] = None


class ProcessingConfig(BaseModel):
    id: int
    project: str
    enabled: bool
    config: ProcessingConfigBody


class AxleSpacingComparison(BaseModel):
    known_m: float
    detected_m: float
    error_m: float


class AxleCalibrationResult(BaseModel):
    measurement: float
    kg_per_strain: Optional[float] = None


class CalibrationEventResult(BaseModel):
    event_code: str
    known_velocity_kmh: float
    estimated_velocity_kmh: float
    velocity_error_kmh: float
    axle_spacings: list[AxleSpacingComparison]
    axle_results: list[AxleCalibrationResult]
    raw_strain_measurement: float
    derived_kg_per_strain: float


class CalibrationResult(BaseModel):
    kg_per_strain: float
    per_event: list[CalibrationEventResult]
    report_url: str


# ── Reprocessing ─────────────────────────────────────────


class ServiceProgress(BaseModel):
    last_completed_index: int = 0
    last_completed_event: Optional[str] = None
    completed_count: int = 0
    updated_at: Optional[datetime] = None


class FailedEvent(BaseModel):
    event: str
    index: int
    message: Optional[str] = None
    failed_at: datetime


class ReprocessingJob(BaseModel):
    job_id: str
    project: str
    requested_by: str
    requested_at: datetime
    time_range_start: datetime
    time_range_end: datetime
    status: str
    total_events: int
    events: list[str]
    progress: dict[str, ServiceProgress] = {}
    failed_events: dict[str, list[FailedEvent]] = {}


class ReprocessingJobSummary(BaseModel):
    job_id: str
    project: str
    requested_by: str
    requested_at: datetime
    time_range_start: datetime
    time_range_end: datetime
    status: str
    total_events: int
    progress: dict[str, ServiceProgress] = {}


# --- TypeAdapters for lists ---
_DetectorSettingsListAdapter = TypeAdapter(list[DetectorSettings])
_ReprocessingJobSummaryListAdapter = TypeAdapter(list[ReprocessingJobSummary])
_EventListAdapter = TypeAdapter(list[Event])


# ── Statistics ───────────────────────────────────────────


class LatestEvent(BaseModel):
    code: str
    start_time: datetime
    end_time: datetime


class EventStatistics(BaseModel):
    n_events_last_week: int
    n_events_last_month: int
    n_events_last_year: int
    n_events_all_time: int
    n_events_in_range: Optional[int] = None
    latest_event: Optional[LatestEvent] = None


class MercutoEventService:
    def __init__(self, client: 'MercutoClient', path: str = '/v2/events') -> None:
        self._client = client
        self._path = path

    # ── Events ───────────────────────────────────────────

    def list_events(self, project: str,
                    limit: int = 50,
                    offset: int = 0,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    ascending: bool = False) -> list[Event]:
        params: PayloadType = {
            'project': project,
            'limit': limit,
            'offset': offset,
            'ascending': ascending,
        }
        if start_time is not None:
            params['start_time'] = start_time.isoformat()
        if end_time is not None:
            params['end_time'] = end_time.isoformat()
        r = self._client.request(f"{self._path}/details", "GET", params=params)
        return _EventListAdapter.validate_json(r.text)

    def create_event(self, project: str,
                     start_time: datetime,
                     end_time: datetime,
                     tags: Optional[list[Tag]] = None) -> Event:
        body: PayloadType = {
            'project': project,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
        }
        if tags is not None:
            body['tags'] = [t.model_dump(mode='json')
                            for t in tags]  # type: ignore[assignment]
        r = self._client.request(f"{self._path}/details", "POST", json=body)
        return Event.model_validate_json(r.text)

    def get_nearest_event(self, project: str, to: datetime) -> Event:
        params: PayloadType = {
            'project': project,
            'to': to.isoformat(),
        }
        r = self._client.request(
            f"{self._path}/search/nearest", "GET", params=params)
        return Event.model_validate_json(r.text)

    def get_event(self, event: str) -> Event:
        r = self._client.request(f"{self._path}/details/{event}", "GET")
        return Event.model_validate_json(r.text)

    def update_event(self, event: str,
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None,
                     tags: Optional[list[Tag]] = None) -> Event:
        body: PayloadType = {}
        if start_time is not None:
            body['start_time'] = start_time.isoformat()
        if end_time is not None:
            body['end_time'] = end_time.isoformat()
        if tags is not None:
            body['tags'] = [t.model_dump(mode='json')
                            for t in tags]  # type: ignore[assignment]
        r = self._client.request(
            f"{self._path}/details/{event}", "PATCH", json=body)
        return Event.model_validate_json(r.text)

    def delete_event(self, event: str) -> None:
        self._client.request(f"{self._path}/details/{event}", "DELETE")

    def set_event_tag(self, event: str, tag_name: str,
                      tag_value: Any = None) -> None:
        body: PayloadType = {'tag_name': tag_name, 'tag_value': tag_value}
        self._client.request(
            f"{self._path}/details/{event}/tags", "PATCH", json=body)

    def reprocess_event(self, event: str) -> ReprocessingJob:
        r = self._client.request(
            f"{self._path}/details/{event}/reprocess", "POST")
        return ReprocessingJob.model_validate_json(r.text)

    def get_next_event(self, event: str, direction: str, step: int = 1) -> Event:
        params: PayloadType = {'direction': direction, 'step': step}
        r = self._client.request(
            f"{self._path}/details/{event}/next", "GET", params=params)
        return Event.model_validate_json(r.text)

    def get_event_status(self, event: str) -> list[EventStatus]:
        r = self._client.request(
            f"{self._path}/details/{event}/status", "GET")
        return [EventStatus.model_validate_json(item) for item in r.json()]

    # ── Detectors ────────────────────────────────────────

    def list_detector_settings(self, project: str) -> list[DetectorSettings]:
        params: PayloadType = {'project': project}
        r = self._client.request(
            f"{self._path}/detectors", "GET", params=params)
        return _DetectorSettingsListAdapter.validate_json(r.text)

    def get_detector_settings(self, detector_id: int) -> DetectorSettings:
        r = self._client.request(
            f"{self._path}/detectors/{detector_id}", "GET")
        return DetectorSettings.model_validate_json(r.text)

    def create_detector(self, project: str,
                        datatables: list[str],
                        enabled: bool = True,
                        config: CronDetectorConfig | GenericDetectorConfig | None = None,
                        ) -> DetectorSettings:
        if config is None:
            config = GenericDetectorConfig()
        body: PayloadType = {
            'project': project,
            'enabled': enabled,
            'config': config.model_dump(mode='json'),
            'datatables': datatables,
        }
        r = self._client.request(f"{self._path}/detectors", "POST", json=body)
        return DetectorSettings.model_validate_json(r.text)

    def update_detector(self, detector_id: int,
                        datatables: list[str],
                        enabled: bool = True,
                        config: CronDetectorConfig | GenericDetectorConfig | None = None,
                        ) -> DetectorSettings:
        if config is None:
            config = GenericDetectorConfig()
        body: PayloadType = {
            'enabled': enabled,
            'datatables': datatables,
            'config': config.model_dump(mode='json'),
        }
        r = self._client.request(
            f"{self._path}/detectors/{detector_id}", "PUT", json=body)
        return DetectorSettings.model_validate_json(r.text)

    def delete_detector(self, detector_id: int) -> None:
        self._client.request(f"{self._path}/detectors/{detector_id}", "DELETE")

    # ── Processing ───────────────────────────────────────

    def get_processing_config(self, project: str) -> ProcessingConfig:
        params: PayloadType = {'project': project}
        r = self._client.request(
            f"{self._path}/processing", "GET", params=params)
        return ProcessingConfig.model_validate_json(r.text)

    def set_processing_config(self, project: str,
                              config: ProcessingConfigBodyIn,
                              enabled: bool = True) -> ProcessingConfig:
        body: PayloadType = {
            'project': project,
            'enabled': enabled,
            'config': config.model_dump(mode='json'),
        }
        r = self._client.request(f"{self._path}/processing", "PUT", json=body)
        return ProcessingConfig.model_validate_json(r.text)

    def calibrate(self, config_id: int,
                  vehicles: list[CalibrationVehicle]) -> CalibrationResult:
        # type: ignore[dict-item]
        body: PayloadType = {'vehicles': [
            v.model_dump(mode='json') for v in vehicles]}
        r = self._client.request(
            f"{self._path}/processing/{config_id}/calibrate", "POST", json=body)
        return CalibrationResult.model_validate_json(r.text)

    # ── Reprocessing ─────────────────────────────────────

    def create_reprocessing_job(self, project: str,
                                time_range_start: datetime,
                                time_range_end: datetime) -> ReprocessingJob:
        body: PayloadType = {
            'project': project,
            'time_range_start': time_range_start.isoformat(),
            'time_range_end': time_range_end.isoformat(),
        }
        r = self._client.request(
            f"{self._path}/reprocessing/jobs", "POST", json=body)
        return ReprocessingJob.model_validate_json(r.text)

    def list_reprocessing_jobs(self, project: str) -> list[ReprocessingJobSummary]:
        params: PayloadType = {'project': project}
        r = self._client.request(
            f"{self._path}/reprocessing/jobs", "GET", params=params)
        return _ReprocessingJobSummaryListAdapter.validate_json(r.text)

    def get_reprocessing_job(self, job_id: str) -> ReprocessingJob:
        r = self._client.request(
            f"{self._path}/reprocessing/jobs/{job_id}", "GET")
        return ReprocessingJob.model_validate_json(r.text)

    def cancel_reprocessing_job(self, job_id: str) -> ReprocessingJob:
        r = self._client.request(
            f"{self._path}/reprocessing/jobs/{job_id}/cancel", "POST")
        return ReprocessingJob.model_validate_json(r.text)

    # ── Statistics ────────────────────────────────────────

    def get_event_statistics(self, project: str,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None) -> EventStatistics:
        params: PayloadType = {'project': project}
        if start_time is not None:
            params['start_time'] = start_time.isoformat()
        if end_time is not None:
            params['end_time'] = end_time.isoformat()
        r = self._client.request(
            f"{self._path}/statistics", "GET", params=params)
        return EventStatistics.model_validate_json(r.text)
