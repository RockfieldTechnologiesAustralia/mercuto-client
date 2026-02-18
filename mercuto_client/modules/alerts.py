from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import AwareDatetime, TypeAdapter

from .data import AggregationInterval, AggregationMethod

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import PayloadType
from ._util import BaseModel


class Healthcheck(BaseModel):
    status: str


class Condition(BaseModel):
    class ConditionAggregationOption(BaseModel):
        method: AggregationMethod
        interval: AggregationInterval
    code: str
    project: str
    description: Optional[str]
    check_type: Literal['event', 'interval']

    match_on: Optional[str] = None
    match_type: Optional[Literal['channel-label-pattern', 'channel-code', 'device-label-pattern',
                                 'device-type-code', 'camera-label-pattern', 'camera-code']] = None
    field: Optional[str] = None
    upper_start_threshold: Optional[float] = None
    lower_start_threshold: Optional[float] = None
    upper_end_threshold: Optional[float] = None
    lower_end_threshold: Optional[float] = None
    aggregation: Optional[ConditionAggregationOption] = None
    duration_threshold: Optional[timedelta] = None
    type: Literal['channel-range', 'channel-offline', 'camera-offline']


class AlarmCondition(BaseModel):
    condition_group: int
    condition: Condition


class Alarm(BaseModel):
    code: str
    project: str
    label: str
    severity: int
    contact_group: Optional[str]
    check_type: Literal['event', 'interval']
    conditions: list[AlarmCondition]


class ConditionLog(BaseModel):
    code: str
    condition: str
    created_at: AwareDatetime
    start_time: AwareDatetime
    end_time: AwareDatetime

    target_code: str
    target_type: Literal['channel', 'camera']
    start_value: Optional[float]
    end_value: Optional[float]
    peak_value: Optional[float]
    peak_time: Optional[AwareDatetime]
    event: Optional[str]
    is_still_active: bool


class AlarmLog(BaseModel):
    code: str
    fired_at: AwareDatetime
    active: bool
    acknowledged_at: Optional[AwareDatetime]
    event: Optional[str]
    severity: int
    alarm: str
    condition_logs: list[ConditionLog]


# --- TypeAdapters for lists ---
_ConditionListAdapter = TypeAdapter(list[Condition])
_AlarmListAdapter = TypeAdapter(list[Alarm])
_ConditionLogListAdapter = TypeAdapter(list[ConditionLog])
_AlarmLogListAdapter = TypeAdapter(list[AlarmLog])


class MercutoAlertService:
    def __init__(self, client: 'MercutoClient', path: str = '/v2/alerts') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # --- Conditions ---
    def list_conditions(self, project: str) -> list[Condition]:
        r = self._client.request(
            f"{self._path}/conditions", "GET", params={"project": project})
        return _ConditionListAdapter.validate_json(r.text)

    def create_condition(self, /, **args: Any) -> Condition:
        r = self._client.request(f"{self._path}/conditions", "POST", json=args)
        return Condition.model_validate_json(r.text)

    def get_condition(self, condition_code: str) -> Condition:
        r = self._client.request(
            f"{self._path}/conditions/{condition_code}", "GET")
        return Condition.model_validate_json(r.text)

    def update_condition(self, condition_code: str, /, **args: Any) -> Condition:
        r = self._client.request(
            f"{self._path}/conditions/{condition_code}", "PUT", json=args)
        return Condition.model_validate_json(r.text)

    def delete_condition(self, condition_code: str) -> None:
        self._client.request(
            f"{self._path}/conditions/{condition_code}", "DELETE")
        return None

    # --- Condition Logs ---
    def list_condition_logs(self, project: str) -> list[ConditionLog]:
        r = self._client.request(
            f"{self._path}/condition-logs", "GET", params={"project": project})
        return _ConditionLogListAdapter.validate_json(r.text)

    # --- Alarms ---
    def list_alarms(self, project: str) -> list[Alarm]:
        r = self._client.request(
            f"{self._path}/alarms", "GET", params={"project": project})
        return _AlarmListAdapter.validate_json(r.text)

    def create_alarm(self, /, **args: Any) -> Alarm:
        r = self._client.request(f"{self._path}/alarms", "POST", json=args)
        return Alarm.model_validate_json(r.text)

    def get_alarm(self, alarm_code: str) -> Alarm:
        r = self._client.request(f"{self._path}/alarms/{alarm_code}", "GET")
        return Alarm.model_validate_json(r.text)

    def update_alarm(self, alarm_code: str, /, **args: Any) -> Alarm:
        r = self._client.request(
            f"{self._path}/alarms/{alarm_code}", "PUT", json=args)
        return Alarm.model_validate_json(r.text)

    def delete_alarm(self, alarm_code: str) -> None:
        self._client.request(f"{self._path}/alarms/{alarm_code}", "DELETE")
        return None

    # --- Alarm Logs ---
    def list_alarm_logs(self, project: str,
                        alarm: Optional[str] = None,
                        acknowledged: Literal['yes', 'no', 'any'] = 'any') -> list[AlarmLog]:
        params: PayloadType = {"project": project,
                               "acknowledged": acknowledged}
        if alarm is not None:
            params["alarm"] = alarm
        r = self._client.request(
            f"{self._path}/alarm-logs", "GET", params=params)
        return _AlarmLogListAdapter.validate_json(r.text)

    def get_alarm_log(self, alarm_log_code: str) -> AlarmLog:
        r = self._client.request(
            f"{self._path}/alarm-logs/{alarm_log_code}", "GET")
        return AlarmLog.model_validate_json(r.text)

    def acknowledge_alarm_log(self, alarm_log_code: str) -> AlarmLog:
        r = self._client.request(
            f"{self._path}/alarm-logs/{alarm_log_code}/acknowledge", "POST")
        return AlarmLog.model_validate_json(r.text)
