import time
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import Field, TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from ..exceptions import MercutoClientException
from . import PayloadType
from ._util import BaseModel

CycleCountSource = Literal['stored', 'computed']
CycleCountSegmentation = Literal['per_event', 'continuous']
CycleCountJobStatus = Literal['pending', 'running', 'finalizing', 'ready', 'failed', 'cancelled']
CoverageBucket = Literal['day', 'week', 'month']


class Healthcheck(BaseModel):
    status: str


# ── Cycle count config ─────────────────────────────────

class CycleCountSettings(BaseModel):
    bin_size: float
    max_bins: int
    multiplier: float
    reservoir_adjustment: bool


class CycleCountRevision(BaseModel):
    revision: int
    bin_size: float
    max_bins: int
    multiplier: float
    reservoir_adjustment: bool
    created_at: datetime
    created_by: Optional[str] = None


class CycleCountChannel(BaseModel):
    channel_code: str
    active: bool
    created_at: datetime


class CycleCountConfig(BaseModel):
    project: str
    revision: CycleCountRevision
    channels: list[CycleCountChannel]
    created_at: datetime
    updated_at: datetime

    def active_channels(self) -> list[str]:
        return [c.channel_code for c in self.channels if c.active]


# ── Stored event cycle counts and coverage ─────────────

class EventCycleCount(BaseModel):
    event_code: str
    channel_code: str
    start_time: datetime
    end_time: datetime
    revision: int
    bins: list[float]
    counts: list[float]
    total_cycles: float
    max_range: float


class CycleCountStatusTotals(BaseModel):
    counted: int
    no_data: int
    failed: int


class ChannelCoverage(BaseModel):
    channel_code: str
    active: bool
    events_counted: int
    total_cycles: float
    max_range: Optional[float] = None


class CoverageBucketCounts(BaseModel):
    bucket_start: datetime
    counted: int
    no_data: int
    failed: int


class CycleCountCoverage(BaseModel):
    project: str
    start_time: datetime
    end_time: datetime
    bucket: CoverageBucket
    totals: CycleCountStatusTotals
    n_project_events: Optional[int] = None
    first_counted_event: Optional[datetime] = None
    last_counted_event: Optional[datetime] = None
    revisions: list[int]
    channels: list[ChannelCoverage]
    buckets: list[CoverageBucketCounts]


# ── Cycle count jobs ───────────────────────────────────

class CycleCountJobRequest(BaseModel):
    channels: list[str]
    start_time: datetime
    end_time: datetime
    source: CycleCountSource
    segmentation: CycleCountSegmentation
    settings: Optional[CycleCountSettings] = None


class CycleCountJobProgress(BaseModel):
    segments_total: int
    segments_done: int
    segments_no_data: int
    segments_failed: int
    rate_per_second: Optional[float] = None
    eta_seconds: Optional[float] = None


class CycleCountJobResult(BaseModel):
    n_rows: int
    parquet_url: str
    csv_url: Optional[str] = None
    summary_url: str
    urls_expire_at: datetime


class CycleCountJob(BaseModel):
    code: str
    project: str
    request: CycleCountJobRequest
    status: CycleCountJobStatus
    message: Optional[str] = None
    requested_by: str
    requested_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: datetime
    progress: CycleCountJobProgress
    result: Optional[CycleCountJobResult] = None

    @property
    def finished(self) -> bool:
        return self.status in ('ready', 'failed', 'cancelled')


# ── Connections ────────────────────────────────────────

class FatigueConnection(BaseModel):
    project: str
    code: str
    label: str
    multiplier: float
    c_d: float
    m: float
    s_0: float
    bs7608_failure_probability: Optional[float] = None
    bs7608_detail_category: Optional[str] = None
    initial_date: datetime
    initial_damage: float
    channels: list[str]


class ConnectionRemnantCapacity(BaseModel):
    connection: FatigueConnection
    remaining_life_years: float = Field(description="Remaining life of the connection in years")
    total_damage: float = Field(description="Total damage accumulated in the connection up to the 'end_time' specified")


_CycleCountRevisionListAdapter = TypeAdapter(list[CycleCountRevision])
_EventCycleCountListAdapter = TypeAdapter(list[EventCycleCount])
_CycleCountJobListAdapter = TypeAdapter(list[CycleCountJob])
_FatigueConnectionListAdapter = TypeAdapter(list[FatigueConnection])
_ConnectionRemnantCapacityListAdapter = TypeAdapter(list[ConnectionRemnantCapacity])


def _connection_payload(project: str, label: str, multiplier: float, c_d: float, m: float, s_0: float,
                        initial_date: datetime, initial_damage: float, channels: list[str],
                        bs7608_failure_probability: Optional[float],
                        bs7608_detail_category: Optional[str]) -> PayloadType:
    return {
        "project": project,
        "label": label,
        "multiplier": multiplier,
        "c_d": c_d,
        "m": m,
        "s_0": s_0,
        "bs7608_failure_probability": bs7608_failure_probability,
        "bs7608_detail_category": bs7608_detail_category,
        "initial_date": initial_date.isoformat(),
        "initial_damage": initial_damage,
        "channels": channels,
    }


class MercutoFatigueService:
    def __init__(self, client: 'MercutoClient', path: str = '/fatigue') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # ── Cycle count config ─────────────────────────────

    def get_cycle_count_config(self, project: str) -> CycleCountConfig:
        r = self._client.request(f"{self._path}/cycle-count-config", "GET", params={"project": project})
        return CycleCountConfig.model_validate_json(r.text)

    def replace_cycle_count_config(self, project: str, settings: CycleCountSettings, channels: list[str]) -> CycleCountConfig:
        payload: PayloadType = {
            "project": project,
            "settings": settings.model_dump(mode='json'),
            "channels": channels,
        }
        r = self._client.request(f"{self._path}/cycle-count-config", "PUT", json=payload)
        return CycleCountConfig.model_validate_json(r.text)

    def list_cycle_count_config_revisions(self, project: str) -> list[CycleCountRevision]:
        r = self._client.request(f"{self._path}/cycle-count-config/revisions", "GET", params={"project": project})
        return _CycleCountRevisionListAdapter.validate_json(r.text)

    # ── Stored event cycle counts ──────────────────────

    def list_event_cycle_counts(self, project: str, start_time: datetime, end_time: datetime,
                                channels: Optional[list[str]] = None, limit: int = 100, offset: int = 0) -> list[EventCycleCount]:
        params: PayloadType = {
            "project": project,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "limit": limit,
            "offset": offset,
        }
        if channels is not None:
            params["channels"] = channels
        r = self._client.request(f"{self._path}/event-cycle-counts", "GET", params=params)
        return _EventCycleCountListAdapter.validate_json(r.text)

    def delete_event_cycle_counts(self, project: str, start_time: datetime, end_time: datetime) -> None:
        params: PayloadType = {"project": project, "start_time": start_time.isoformat(), "end_time": end_time.isoformat()}
        self._client.request(f"{self._path}/event-cycle-counts", "DELETE", params=params)

    def get_cycle_count_coverage(self, project: str, start_time: datetime, end_time: datetime,
                                 bucket: CoverageBucket = 'day') -> CycleCountCoverage:
        params: PayloadType = {
            "project": project,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "bucket": bucket,
        }
        r = self._client.request(f"{self._path}/cycle-count-coverage", "GET", params=params)
        return CycleCountCoverage.model_validate_json(r.text)

    # ── Cycle count jobs ───────────────────────────────

    def create_cycle_count_job(self, project: str, channels: list[str], start_time: datetime, end_time: datetime,
                               source: CycleCountSource, segmentation: CycleCountSegmentation = 'per_event',
                               settings: Optional[CycleCountSettings] = None, timeout: float = 0) -> CycleCountJob:
        payload: PayloadType = {
            "project": project,
            "channels": channels,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "source": source,
            "segmentation": segmentation,
        }
        if settings is not None:
            payload["settings"] = settings.model_dump(mode='json')
        r = self._client.request(f"{self._path}/cycle-count-jobs", "POST", json=payload, params={"timeout": timeout})
        return CycleCountJob.model_validate_json(r.text)

    def list_cycle_count_jobs(self, project: str, limit: int = 50, offset: int = 0) -> list[CycleCountJob]:
        params: PayloadType = {"project": project, "limit": limit, "offset": offset}
        r = self._client.request(f"{self._path}/cycle-count-jobs", "GET", params=params)
        return _CycleCountJobListAdapter.validate_json(r.text)

    def get_cycle_count_job(self, code: str) -> CycleCountJob:
        r = self._client.request(f"{self._path}/cycle-count-jobs/{code}", "GET")
        return CycleCountJob.model_validate_json(r.text)

    def cancel_cycle_count_job(self, code: str) -> CycleCountJob:
        r = self._client.request(f"{self._path}/cycle-count-jobs/{code}/cancel", "POST")
        return CycleCountJob.model_validate_json(r.text)

    def delete_cycle_count_job(self, code: str) -> None:
        self._client.request(f"{self._path}/cycle-count-jobs/{code}", "DELETE")

    def wait_for_cycle_count_job(self, code: str, timeout: float = 600, poll_interval: float = 2) -> CycleCountJob:
        """Poll a job until it finishes. Raises if it has not finished within ``timeout`` seconds."""
        deadline = time.monotonic() + timeout
        while True:
            job = self.get_cycle_count_job(code)
            if job.finished:
                return job
            if time.monotonic() > deadline:
                raise MercutoClientException(f"Cycle count job {code} did not finish within {timeout} seconds")
            time.sleep(poll_interval)

    # ── Connections ────────────────────────────────────

    def list_connections(self, project: str) -> list[FatigueConnection]:
        r = self._client.request(f"{self._path}/connections", "GET", params={"project": project})
        return _FatigueConnectionListAdapter.validate_json(r.text)

    def get_connection(self, code: str) -> FatigueConnection:
        r = self._client.request(f"{self._path}/connections/{code}", "GET")
        return FatigueConnection.model_validate_json(r.text)

    def create_connection(self, project: str, label: str, multiplier: float, c_d: float, m: float, s_0: float,
                          initial_date: datetime, initial_damage: float, channels: list[str],
                          bs7608_failure_probability: Optional[float] = None,
                          bs7608_detail_category: Optional[str] = None) -> FatigueConnection:
        payload = _connection_payload(project, label, multiplier, c_d, m, s_0, initial_date, initial_damage, channels,
                                      bs7608_failure_probability, bs7608_detail_category)
        r = self._client.request(f"{self._path}/connections", "POST", json=payload)
        return FatigueConnection.model_validate_json(r.text)

    def replace_connection(self, code: str, project: str, label: str, multiplier: float, c_d: float, m: float, s_0: float,
                           initial_date: datetime, initial_damage: float, channels: list[str],
                           bs7608_failure_probability: Optional[float] = None,
                           bs7608_detail_category: Optional[str] = None) -> FatigueConnection:
        payload = _connection_payload(project, label, multiplier, c_d, m, s_0, initial_date, initial_damage, channels,
                                      bs7608_failure_probability, bs7608_detail_category)
        r = self._client.request(f"{self._path}/connections/{code}", "PUT", json=payload)
        return FatigueConnection.model_validate_json(r.text)

    def delete_connection(self, code: str) -> None:
        self._client.request(f"{self._path}/connections/{code}", "DELETE")

    def list_remnant_capacities(self, project: str, start_time: datetime, end_time: datetime,
                                connections: Optional[list[str]] = None) -> list[ConnectionRemnantCapacity]:
        params: PayloadType = {"project": project, "start_time": start_time.isoformat(), "end_time": end_time.isoformat()}
        if connections is not None:
            params["connections"] = connections
        r = self._client.request(f"{self._path}/remnant-capacities", "GET", params=params)
        return _ConnectionRemnantCapacityListAdapter.validate_json(r.text)
