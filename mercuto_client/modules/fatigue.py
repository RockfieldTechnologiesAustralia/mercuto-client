import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal, Optional

import requests as _requests
from pydantic import TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from ..exceptions import MercutoClientException
from . import PayloadType
from ._util import BaseModel

FatigueJobStatus = Literal['pending', 'running', 'ready', 'failed', 'cancelled']
EventOutcome = Literal['stored', 'counted', 'no_data', 'failed']


class Healthcheck(BaseModel):
    status: str


# ── Cycle count config ─────────────────────────────────

class CycleCountSettings(BaseModel):
    bin_size: float
    max_bins: int
    multiplier: float
    reservoir_adjustment: bool


class CycleCountConfig(BaseModel):
    project: str
    settings: CycleCountSettings
    channels: list[str]


# ── Stored cycle counts ────────────────────────────────

class ChannelCycleCounts(BaseModel):
    channel_code: str
    bins: list[float]
    counts: list[float]
    total_cycles: float
    max_range: Optional[float] = None


class EventCycleCounts(BaseModel):
    project: str
    event_code: str
    start_time: datetime
    end_time: datetime
    settings: CycleCountSettings
    channels: list[ChannelCycleCounts]


class ChannelCycleCountStats(BaseModel):
    channel_code: str
    events_stored: int


class CycleCountStats(BaseModel):
    project: str
    start_time: datetime
    end_time: datetime
    n_project_events: Optional[int] = None
    events_stored: int
    first_stored_event: Optional[datetime] = None
    last_stored_event: Optional[datetime] = None
    channels: list[ChannelCycleCountStats]


# ── Fatigue jobs ───────────────────────────────────────

class FatigueJobProgress(BaseModel):
    events_total: int
    events_done: int
    rate_per_second: Optional[float] = None
    eta_seconds: Optional[float] = None


class FatigueJob(BaseModel):
    code: str
    project: str
    label: str
    start_time: datetime
    end_time: datetime
    settings: CycleCountSettings
    channels: list[str]
    status: FatigueJobStatus
    message: Optional[str] = None
    requested_by: str
    requested_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: datetime
    progress: FatigueJobProgress
    result_url: Optional[str] = None
    result_url_expires_at: Optional[datetime] = None

    @property
    def finished(self) -> bool:
        return self.status in ('ready', 'failed', 'cancelled')


class FatigueJobEventFailure(BaseModel):
    start_time: datetime
    event_code: str
    status: EventOutcome
    message: Optional[str] = None


class FatigueJobEventTotals(BaseModel):
    stored: int
    counted: int
    no_data: int
    failed: int
    failures: list[FatigueJobEventFailure]


class FatigueJobChannelResult(BaseModel):
    channel_code: str
    events_counted: int
    total_cycles: float
    max_range: Optional[float] = None
    root_sum_cubed: Optional[float] = None
    bins: list[float]
    counts: list[float]
    days: list[date]
    daily_cycles: list[float]
    daily_sum_cubed: list[float]


class FatigueJobConnectionResult(BaseModel):
    code: str
    label: str
    channels: list[str]
    multiplier: float
    c_d: float
    m: float
    s_0: float
    initial_date: datetime
    initial_damage: float
    days: list[date]
    daily_damage: list[float]
    damage_in_range: float
    damage_at_start: float
    damage_at_end: float
    remaining_life_years: Optional[float] = None


class FatigueJobResult(BaseModel):
    code: str
    project: str
    label: str
    start_time: datetime
    end_time: datetime
    settings: CycleCountSettings
    first_event_start: Optional[datetime] = None
    last_event_start: Optional[datetime] = None
    events: FatigueJobEventTotals
    channels: list[FatigueJobChannelResult]
    connections: list[FatigueJobConnectionResult]


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


_FatigueJobListAdapter = TypeAdapter(list[FatigueJob])
_FatigueConnectionListAdapter = TypeAdapter(list[FatigueConnection])


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
        """Changing the settings deletes all stored cycle counts of the project."""
        payload: PayloadType = {
            "project": project,
            "settings": settings.model_dump(mode='json'),
            "channels": channels,
        }
        r = self._client.request(f"{self._path}/cycle-count-config", "PUT", json=payload)
        return CycleCountConfig.model_validate_json(r.text)

    # ── Stored cycle counts ────────────────────────────

    def get_cycle_count_stats(self, project: str, start_time: datetime, end_time: datetime) -> CycleCountStats:
        params: PayloadType = {"project": project, "start_time": start_time.isoformat(), "end_time": end_time.isoformat()}
        r = self._client.request(f"{self._path}/cycle-count-stats", "GET", params=params)
        return CycleCountStats.model_validate_json(r.text)

    def get_event_cycle_counts(self, project: str, event: str) -> EventCycleCounts:
        """Cycle counts of one event; channels without stored counts are counted and stored."""
        r = self._client.request(f"{self._path}/event-cycle-counts/{event}", "GET", params={"project": project})
        return EventCycleCounts.model_validate_json(r.text)

    # ── Fatigue jobs ───────────────────────────────────

    def create_job(self, project: str, label: str, start_time: datetime, end_time: datetime) -> FatigueJob:
        payload: PayloadType = {
            "project": project,
            "label": label,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        r = self._client.request(f"{self._path}/jobs", "POST", json=payload)
        return FatigueJob.model_validate_json(r.text)

    def list_jobs(self, project: str, limit: int = 50, offset: int = 0) -> list[FatigueJob]:
        params: PayloadType = {"project": project, "limit": limit, "offset": offset}
        r = self._client.request(f"{self._path}/jobs", "GET", params=params)
        return _FatigueJobListAdapter.validate_json(r.text)

    def get_job(self, code: str) -> FatigueJob:
        r = self._client.request(f"{self._path}/jobs/{code}", "GET")
        return FatigueJob.model_validate_json(r.text)

    def cancel_job(self, code: str) -> FatigueJob:
        r = self._client.request(f"{self._path}/jobs/{code}/cancel", "POST")
        return FatigueJob.model_validate_json(r.text)

    def delete_job(self, code: str) -> None:
        self._client.request(f"{self._path}/jobs/{code}", "DELETE")

    def wait_for_job(self, code: str, timeout: float = 600, poll_interval: float = 2) -> FatigueJob:
        """Poll a job until it finishes. Raises if it has not finished within ``timeout`` seconds."""
        deadline = time.monotonic() + timeout
        while True:
            job = self.get_job(code)
            if job.finished:
                return job
            if time.monotonic() > deadline:
                raise MercutoClientException(f"Fatigue job {code} did not finish within {timeout} seconds")
            time.sleep(poll_interval)

    def get_job_result(self, code: str) -> FatigueJobResult:
        """Download the result of a `ready` job."""
        job = self.get_job(code)
        if job.result_url is None:
            raise MercutoClientException(f"Fatigue job {code} has no result ({job.status})")
        response = _requests.get(job.result_url, timeout=60)
        response.raise_for_status()
        return FatigueJobResult.model_validate_json(response.content)

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
