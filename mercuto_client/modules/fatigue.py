from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import Field, TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import _PayloadType
from ._util import BaseModel


class RainflowConfiguration(BaseModel):
    project: str
    max_bins: int
    bin_size: float
    multiplier: float
    reservoir_adjustment: bool
    sources: list[str]


class FatigueConnection(BaseModel):
    project: str
    code: str
    label: str
    multiplier: float
    c_d: float
    m: float
    s_0: float
    bs7608_failure_probability: Optional[float]
    bs7608_detail_category: Optional[str]
    initial_date: datetime
    initial_damage: float
    sources: list[str]


class ConnectionRemnantCapacity(BaseModel):
    connection: FatigueConnection
    remaining_life_years: float = Field(description="Remaining life of the connection in years")
    total_damage: float = Field(description="Total damage accumulated in the connection up to the 'end_time' specified")


class Healthcheck(BaseModel):
    status: str


_RainflowConfigurationlistAdapter = TypeAdapter(list[RainflowConfiguration])
_FatigueConnectionlistAdapter = TypeAdapter(list[FatigueConnection])
_ConnectionRemnantCapacitylistAdapter = TypeAdapter(list[ConnectionRemnantCapacity])


class MercutoFatigueService:
    def __init__(self, client: 'MercutoClient', path: str = '/fatigue') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client._http_request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # --- Rainflow routes ---

    def list_rainflow_config(self, project: str) -> list[RainflowConfiguration]:
        params: _PayloadType = {"project": project}
        r = self._client._http_request(f"{self._path}/rainflow/setup", "GET", params=params)
        return _RainflowConfigurationlistAdapter.validate_json(r.text)

    def setup_rainflow(
        self,
        project: str,
        max_bins: int,
        bin_size: float,
        multiplier: float,
        reservoir_adjustment: bool,
        sources: list[str]
    ) -> RainflowConfiguration:
        payload: _PayloadType = {
            "project": project,
            "max_bins": max_bins,
            "bin_size": bin_size,
            "multiplier": multiplier,
            "reservoir_adjustment": reservoir_adjustment,
            "sources": sources,
        }
        r = self._client._http_request(f"{self._path}/rainflow/setup", "PUT", json=payload)
        return RainflowConfiguration.model_validate_json(r.text)

    def get_cycle_counts(
        self, project: str, start_time: datetime, end_time: datetime
    ) -> bytes:
        params: _PayloadType = {
            "project": project,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        r = self._client._http_request(
            f"{self._path}/rainflow/cycle_counts", "GET", params=params, stream=True
        )
        return r.content

    def delete_cycle_counts(
        self, project: str, start_time: datetime, end_time: datetime, ignore_if_not_configured: bool = False
    ) -> None:
        params: _PayloadType = {
            "project": project,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "ignore_if_not_configured": ignore_if_not_configured,
        }
        self._client._http_request(
            f"{self._path}/rainflow/cycle_counts", "DELETE", params=params
        )

    def calculate_cycle_counts(
        self,
        project: str,
        event: str,
        presigned_url: str,
        mime_type: Literal['application/feather'],
        url_expiry: Optional[datetime] = None,
        ignore_if_not_configured: bool = False
    ) -> None:
        payload: _PayloadType = {
            "project": project,
            "event": event,
            "presigned_url": presigned_url,
            "mime_type": mime_type,
        }
        if url_expiry is not None:
            payload["url_expiry"] = url_expiry.isoformat()
        params = {"ignore_if_not_configured": ignore_if_not_configured}
        self._client._http_request(
            f"{self._path}/rainflow/cycle_counts/calculate", "PUT", json=payload, params=params
        )

    # --- Fatigue Connections routes ---

    def get_connections(self, project: str) -> list[FatigueConnection]:
        params: _PayloadType = {"project": project}
        r = self._client._http_request(f"{self._path}/connections", "GET", params=params)
        return _FatigueConnectionlistAdapter.validate_json(r.text)

    def add_connection(
        self,
        project: str,
        label: str,
        multiplier: float,
        c_d: float,
        m: float,
        s_0: float,
        bs7608_failure_probability: float,
        bs7608_detail_category: str,
        initial_date: datetime,
        initial_damage: float,
        sources: list[str]
    ) -> FatigueConnection:
        payload: _PayloadType = {
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
            "sources": sources,
        }
        r = self._client._http_request(f"{self._path}/connections", "PUT", json=payload)
        return FatigueConnection.model_validate_json(r.text)

    def delete_connection(self, connection_code: str) -> None:
        self._client._http_request(f"{self._path}/connections/{connection_code}", "DELETE")

    # --- Connection Data routes ---

    def get_connection_remnant_capacity(
        self, project: str, start_time: datetime, end_time: datetime
    ) -> list[ConnectionRemnantCapacity]:
        params: _PayloadType = {
            "project": project,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        r = self._client._http_request(
            f"{self._path}/connection_data/remnant-capacity", "GET", params=params
        )
        return _ConnectionRemnantCapacitylistAdapter.validate_json(r.text)
