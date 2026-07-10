from enum import Enum
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import AwareDatetime, TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import PayloadType
from ._util import BaseModel


class Healthcheck(BaseModel):
    status: str


# ── Action types ─────────────────────────────────────────

class ActionType(str, Enum):
    """The kind of work a schedule performs when it fires."""
    FILE_COLLECTION = 'file-collection'


RunStatus = Literal['pending', 'running', 'succeeded', 'failed', 'skipped', 'timed_out']


# ── File collection ──────────────────────────────────────

class FileCollectionConfig(BaseModel):
    """Response view of a file-collection config. Credentials are omitted."""
    type: Literal[ActionType.FILE_COLLECTION] = ActionType.FILE_COLLECTION
    uri: str
    source_pattern: str
    datatable: str


class FileCollectionConfigIn(FileCollectionConfig):
    """
    Configuration for a file-collection action.

    Credentials are write-only: they are accepted here and persisted, but never returned in a
    response. On update, a credential that is omitted keeps its previously stored value; one
    passed explicitly (even as null) overwrites it.
    """
    type: Literal[ActionType.FILE_COLLECTION] = ActionType.FILE_COLLECTION
    uri: str
    source_pattern: str
    datatable: str

    # FTP credentials
    username: Optional[str] = None
    password: Optional[str] = None

    # S3-style credentials
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None


class FileCollectionResult(BaseModel):
    """Summary of a file-collection run's result."""
    type: Literal[ActionType.FILE_COLLECTION] = ActionType.FILE_COLLECTION
    collected_count: int
    skipped_count: int
    collected_files: list[str] = []


# Currently the file-collection action is the only type. When a second action type is added,
# turn these into discriminated unions keyed on `type`.
ScheduleConfigIn = FileCollectionConfigIn
ScheduleConfig = FileCollectionConfig
ActionRunResult = FileCollectionResult


# ── Schedules ────────────────────────────────────────────


class Schedule(BaseModel):
    code: str
    project: str
    cron: str
    timezone: str
    enabled: bool
    last_triggered_at: Optional[AwareDatetime] = None
    label: Optional[str] = None
    config: ScheduleConfig
    created_at: AwareDatetime
    updated_at: AwareDatetime


# ── Runs ─────────────────────────────────────────────────


class RunOut(BaseModel):
    scheduled_at: AwareDatetime
    started_at: Optional[AwareDatetime] = None
    finished_at: Optional[AwareDatetime] = None
    status: RunStatus
    result: Optional[ActionRunResult] = None
    error: Optional[str] = None
    created_at: AwareDatetime


# --- TypeAdapters for lists ---
_ScheduleListAdapter = TypeAdapter(list[Schedule])
_RunOutListAdapter = TypeAdapter(list[RunOut])


class MercutoActionService:
    def __init__(self, client: 'MercutoClient', path: str = '/actions') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # ── Schedules ────────────────────────────────────────

    def list_schedules(self, project: str) -> list[Schedule]:
        params: PayloadType = {'project': project}
        r = self._client.request(
            f"{self._path}/schedules", "GET", params=params)
        return _ScheduleListAdapter.validate_json(r.text)

    def create_schedule(self, project: str,
                        cron: str,
                        config: ScheduleConfigIn,
                        timezone: str = 'UTC',
                        enabled: bool = True,
                        label: Optional[str] = None) -> Schedule:
        body: PayloadType = {
            'project': project,
            'cron': cron,
            'timezone': timezone,
            'enabled': enabled,
            'config': config.model_dump(mode='json'),
        }
        if label is not None:
            body['label'] = label
        r = self._client.request(f"{self._path}/schedules", "POST", json=body)
        return Schedule.model_validate_json(r.text)

    def get_schedule(self, schedule_code: str) -> Schedule:
        r = self._client.request(
            f"{self._path}/schedules/{schedule_code}", "GET")
        return Schedule.model_validate_json(r.text)

    def update_schedule(self, schedule_code: str,
                        cron: str,
                        config: ScheduleConfigIn,
                        timezone: str = 'UTC',
                        enabled: bool = True,
                        label: Optional[str] = None) -> Schedule:
        body: PayloadType = {
            'cron': cron,
            'timezone': timezone,
            'enabled': enabled,
            'config': config.model_dump(mode='json'),
        }
        if label is not None:
            body['label'] = label
        r = self._client.request(
            f"{self._path}/schedules/{schedule_code}", "PATCH", json=body)
        return Schedule.model_validate_json(r.text)

    def delete_schedule(self, schedule_code: str) -> None:
        self._client.request(
            f"{self._path}/schedules/{schedule_code}", "DELETE")

    # ── Run logs ─────────────────────────────────────────

    def list_run_logs(self, schedule_code: str) -> list[RunOut]:
        r = self._client.request(
            f"{self._path}/schedules/{schedule_code}/logs", "GET")
        return _RunOutListAdapter.validate_json(r.text)

    # ── Manual runs ──────────────────────────────────────

    def trigger_run(self, schedule_code: str) -> RunOut:
        r = self._client.request(
            f"{self._path}/schedules/{schedule_code}/run", "POST")
        return RunOut.model_validate_json(r.text)
