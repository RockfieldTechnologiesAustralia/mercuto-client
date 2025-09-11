import enum
import os
import time
from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import (TYPE_CHECKING, Any, BinaryIO, Collection, Literal,
                    Optional, TextIO)

from pydantic import TypeAdapter

from ..exceptions import MercutoClientException, MercutoHTTPException
from ..util import batched
from . import _PayloadType, _raise_for_response
from ._util import BaseModel, serialise_timedelta

if TYPE_CHECKING:
    from ..client import MercutoClient


class ChannelClassification(enum.Enum):
    PRIMARY = 'PRIMARY'
    PRIMARY_EVENT_AGGREGATE = 'PRIMARY_EVENT_AGGREGATE'
    EVENT_METRIC = 'EVENT_METRIC'
    SECONDARY = 'SECONDARY'


class Units(BaseModel):
    code: str
    name: str
    unit: Optional[str]


class Channel(BaseModel):
    code: str
    project: str
    units: Optional[Units]
    sampling_period: Optional[timedelta]
    classification: ChannelClassification
    label: str
    metric: Optional[str]
    source: Optional[str]
    aggregate: Optional[str]
    value_range_min: Optional[float]
    value_range_max: Optional[float]
    multiplier: float
    offset: float
    last_valid_timestamp: Optional[datetime]
    is_wallclock_interval: bool


class Expression(BaseModel):
    expression: str
    target: Channel


class DatatableColumn(BaseModel):
    channel: str
    column_label: str


class Datatable(BaseModel):
    code: str
    project: str
    name: str
    enabled: bool
    sampling_period: Optional[timedelta] = None
    columns: list[DatatableColumn]


class SecondaryDataSample(BaseModel):
    channel: str
    timestamp: datetime
    value: float


class MetricDataSample(BaseModel):
    channel: str
    timestamp: datetime
    value: float
    event: str


class LatestDataSample(BaseModel):
    channel: str
    timestamp: datetime
    value: float


_ChannellistAdapter = TypeAdapter(list[Channel])
_ExpressionlistAdapter = TypeAdapter(list[Expression])
_DatatablelistAdapter = TypeAdapter(list[Datatable])
_UnitslistAdapter = TypeAdapter(list[Units])
_MetricSamplelistAdapter = TypeAdapter(list[MetricDataSample])
_SecondarySamplelistAdapter = TypeAdapter(list[SecondaryDataSample])
_LatestSampleListAdapter = TypeAdapter(list[LatestDataSample])


class FrameFormat(enum.Enum):
    COLUMNS = "COLUMNS"
    SAMPLES = "SAMPLES"


class FileFormat(enum.Enum):
    FEATHER = "FEATHER"
    PARQUET = "PARQUET"
    CSV = "CSV"


class ChannelFormat(enum.Enum):
    CODE = "CODE"
    LABEL = "LABEL"


class AggregationOptions(BaseModel):
    method: Literal['min', 'max', 'mean', 'sum', 'count', 'greatest']
    interval: Literal['second', 'minute', 'hour', 'day', 'week', 'month', 'year']
    rolling: bool = False


class GetStatusRequestResponse(BaseModel):
    class GetDataRequestStatusCompletedResult(BaseModel):
        class ResultMetadata(BaseModel):
            first_timestamp: Optional[datetime]
        result_url: str
        expires_at: datetime
        mime_type: str
        file_size: int
        metadata: ResultMetadata

    request_id: str
    status_code: int
    message: str
    requested_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional["GetStatusRequestResponse.GetDataRequestStatusCompletedResult"]


class Healthcheck(BaseModel):
    status: str


class MercutoDataService:
    def __init__(self, client: 'MercutoClient', path: str = '/v2/data') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client._http_request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    def refresh_continuous_aggregates(self) -> None:
        """
        Request a refresh of continuous aggregates on all tables
        """
        self._client._http_request(f"{self._path}/meta/refresh-aggregates", "POST")

    """
    Channels
    """

    def list_channels(self, project: str, classification: Optional[ChannelClassification] = None,
                      aggregate: Optional[str] = None, metric: Optional[str] = None,
                      show_hidden: bool = False) -> list[Channel]:
        params: dict[str, Any] = {
            'project': project,
            'limit': 100,
            'offset': 0,
            'show_hidden': show_hidden,
        }
        if classification:
            params['classification'] = classification.value
        if aggregate:
            params['aggregate'] = aggregate
        if metric:
            params['metric'] = metric

        all_channels = []
        while True:
            r = self._client._http_request(f'{self._path}/channels', 'GET', params=params)

            channels = _ChannellistAdapter.validate_json(r.text)
            all_channels.extend(channels)
            if len(channels) < params['limit']:
                break
            params['offset'] += params['limit']
        return all_channels

    def get_channel(self, code: str) -> Optional[Channel]:
        r = self._client._http_request(f'{self._path}/channels/{code}', 'GET', raise_for_status=False)
        if r.status_code == 404:
            return None
        _raise_for_response(r)
        return Channel.model_validate_json(r.text)

    def update_channel(self, code: str, label: Optional[str] = None, units: Optional[str] = None,
                       metric: Optional[str] = None, multiplier: Optional[float] = None,
                       offset: Optional[float] = None) -> Channel:
        payload: _PayloadType = {}
        if label is not None:
            payload['label'] = label
        if units is not None:
            payload['units'] = units
        if metric is not None:
            payload['metric'] = metric
        if multiplier is not None:
            payload['multiplier'] = multiplier
        if offset is not None:
            payload['offset'] = offset

        r = self._client._http_request(f'{self._path}/channels/{code}', 'PATCH', json=payload)
        return Channel.model_validate_json(r.text)

    def delete_channel(self, code: str) -> bool:
        r = self._client._http_request(f'{self._path}/channels/{code}', 'DELETE')
        return r.status_code == 204

    def create_channel(self, project: str,
                       label: str,
                       classification: ChannelClassification = ChannelClassification.SECONDARY,
                       sampling_period: Optional[timedelta] = None,
                       multiplier: float = 1.0, offset: float = 0.0,
                       value_range_min: Optional[float] = None, value_range_max: Optional[float] = None,
                       delta_max: Optional[float] = None,
                       units: Optional[str] = None,
                       aggregate: Optional[str] = None,
                       source: Optional[str] = None,
                       metric: Optional[str] = None) -> Channel:
        payload: _PayloadType = {
            'project': project,
            'label': label,
            'classification': classification.value,
            'multiplier': multiplier,
            'offset': offset,
        }
        if sampling_period is not None:
            payload['sampling_period'] = serialise_timedelta(sampling_period)
        if value_range_min is not None:
            payload['value_range_min'] = value_range_min
        if value_range_max is not None:
            payload['value_range_max'] = value_range_max
        if delta_max is not None:
            payload['delta_max'] = delta_max
        if units is not None:
            payload['units'] = units
        if aggregate is not None:
            payload['aggregate'] = aggregate
        if source is not None:
            payload['source'] = source
        if metric is not None:
            payload['metric'] = metric

        r = self._client._http_request(f'{self._path}/channels', 'PUT', json=payload)
        return Channel.model_validate_json(r.text)

    """
    Expressions
    """

    def create_expression(
        self,
        project: str,
        label: str,
        expression: str,
        units: Optional[str] = None,
        aggregate: Optional[str] = None,
        metric: Optional[str] = None
    ) -> Expression:
        payload: _PayloadType = {
            "project": project,
            "label": label,
            "expression": expression,
        }
        if units is not None:
            payload["units"] = units
        if aggregate is not None:
            payload["aggregate"] = aggregate
        if metric is not None:
            payload["metric"] = metric

        r = self._client._http_request(f'{self._path}/expressions', 'PUT', json=payload)
        return Expression.model_validate_json(r.text)

    def delete_expression(self, code: str) -> bool:
        r = self._client._http_request(f'{self._path}/expressions/{code}', 'DELETE')
        return r.status_code == 202

    """
    Datatables
    """

    def create_datatable(self, project: str, name: str, sampling_period: timedelta, column_labels: Collection[str]) -> Datatable:
        payload: _PayloadType = {
            "project": project,
            "name": name,
            "sampling_period": serialise_timedelta(sampling_period),
            "column_labels": list(column_labels),
        }
        r = self._client._http_request(f'{self._path}/datatables', 'PUT', json=payload)
        return Datatable.model_validate_json(r.text)

    def list_datatables(self, project: str) -> list[Datatable]:
        datatables = []
        params: dict[str, Any] = {
            "project": project,
            "limit": 100,
            "offset": 0,
        }
        while True:
            r = self._client._http_request(f'{self._path}/datatables', 'GET', params=params)

            batch = _DatatablelistAdapter.validate_json(r.text)
            datatables.extend(batch)
            if len(batch) < params["limit"]:
                break
            params["offset"] += params["limit"]
        return datatables

    """
    Units
    """

    def list_units(self) -> list[Units]:
        r = self._client._http_request(f'{self._path}/units', 'GET')
        return _UnitslistAdapter.validate_json(r.text)

    def create_unit(self, name: str, unit: str) -> Units:
        payload: _PayloadType = {
            "name": name,
            "unit": unit,
        }
        r = self._client._http_request(f'{self._path}/units', 'PUT', json=payload)
        return Units.model_validate_json(r.text)

    """
    Requests
    """

    def create_request(
        self,
        start_time: datetime,
        end_time: datetime,
        project: Optional[str] = None,
        channels: Optional[Collection[str]] = None,
        classification: Optional[ChannelClassification] = None,
        frame_format: FrameFormat = FrameFormat.SAMPLES,
        file_format: FileFormat = FileFormat.PARQUET,
        channel_format: ChannelFormat = ChannelFormat.CODE,
        aggregation: Optional[AggregationOptions] = None,
        timeout: float = 0
    ) -> GetStatusRequestResponse:
        if timeout > 20:
            timeout = 20  # Cap timeout to 20 seconds

        if channels is None and classification is None:
            raise ValueError("Must supply either channels or classification.")

        payload: _PayloadType = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "frame_format": frame_format.value,
            "file_format": file_format.value,
            "channel_format": channel_format.value,
        }

        if project:
            payload["project"] = project

        if channels:
            payload["channels"] = list(channels)

        if classification:
            payload["classification"] = classification.value

        if aggregation is not None:
            payload["aggregation"] = aggregation.model_dump(mode='json')

        r = self._client._http_request(
            f'{self._path}/requests', 'POST',
            json=payload,
            params={"timeout": timeout}
        )
        return GetStatusRequestResponse.model_validate_json(r.text)

    def get_request(self, request_id: str) -> GetStatusRequestResponse:
        r = self._client._http_request(f'{self._path}/requests/{request_id}', 'GET')
        return GetStatusRequestResponse.model_validate_json(r.text)

    """
    Request Helpers
    """

    def load_presigned_url(
        self,
        start_time: datetime,
        end_time: datetime,
        project: Optional[str] = None,
        channels: Optional[Collection[str]] = None,
        classification: Optional[ChannelClassification] = None,
        frame_format: FrameFormat = FrameFormat.SAMPLES,
        file_format: FileFormat = FileFormat.PARQUET,
        channel_format: ChannelFormat = ChannelFormat.CODE,
        aggregation: Optional[AggregationOptions] = None,
        poll_interval: float = 0.25,
        timeout: int = 60
    ) -> str:
        """
        Request a presigned download URL for data and poll until ready.

        Returns:
            The presigned result_url as a string.
        Raises:
            MercutoHTTPException, MercutoClientException on error or timeout.
        """

        result = self.load_data_request(
            start_time=start_time,
            end_time=end_time,
            project=project,
            channels=channels,
            classification=classification,
            frame_format=frame_format,
            file_format=file_format,
            channel_format=channel_format,
            aggregation=aggregation,
            poll_interval=poll_interval,
            timeout=timeout
        )
        if result.result_url is None:
            raise MercutoClientException("Failed to obtain presigned URL.")
        return result.result_url

    def load_data_request(
        self,
        start_time: datetime,
        end_time: datetime,
        project: Optional[str] = None,
        channels: Optional[Collection[str]] = None,
        classification: Optional[ChannelClassification] = None,
        frame_format: FrameFormat = FrameFormat.SAMPLES,
        file_format: FileFormat = FileFormat.PARQUET,
        channel_format: ChannelFormat = ChannelFormat.CODE,
        aggregation: Optional[AggregationOptions] = None,
        poll_interval: float = 0.25,
        timeout: int = 60
    ) -> GetStatusRequestResponse.GetDataRequestStatusCompletedResult:
        """
        Request a presigned download URL for data and poll until ready.

        Returns:
            The GetStatusRequestResponse
        Raises:
            MercutoHTTPException, MercutoClientException on error or timeout.
        """

        # Start the request, using poll_interval as the initial timeout
        status = self.create_request(
            project=project,
            channels=channels,
            start_time=start_time,
            end_time=end_time,
            classification=classification,
            frame_format=frame_format,
            file_format=file_format,
            channel_format=channel_format,
            timeout=poll_interval,
            aggregation=aggregation
        )
        request_id = status.request_id

        # If already complete, return immediately
        if status.status_code == 200 and status.result and status.result.result_url:
            return status.result
        if status.status_code >= 400:
            raise MercutoHTTPException(status.message, status.status_code)

        # Otherwise, poll for completion
        start_poll = time.time()
        while True:
            status = self.get_request(request_id)
            if status.status_code == 200 and status.result and status.result.result_url:
                return status.result
            if status.status_code >= 400:
                raise MercutoHTTPException(status.message, status.status_code)
            if time.time() - start_poll > timeout:
                raise MercutoClientException("Timed out waiting for presigned url.")
            time.sleep(poll_interval)

    """
    Samples
    """

    def insert_secondary_samples(
        self,
        project: str,
        samples: Collection[SecondaryDataSample]
    ) -> None:
        """
        Insert secondary samples.
        """
        for batch in batched(samples, 5000):
            payload = _SecondarySamplelistAdapter.dump_python(list(batch), mode='json')
            self._client._http_request(
                f'{self._path}/samples/secondary', 'PUT', json=payload, params={"project": project}
            )

            # No return value, 202 accepted

    def insert_metric_samples(
        self,
        project: str,
        samples: Collection[MetricDataSample]
    ) -> None:
        """
        Insert metric samples.
        """
        for batch in batched(samples, 5000):
            payload = _MetricSamplelistAdapter.dump_python(list(batch), mode='json')
            self._client._http_request(
                f'{self._path}/samples/metric', 'PUT', json=payload, params={"project": project}
            )

        # No return value, 202 accepted

    def load_secondary_samples(
        self,
        channels: Collection[str],
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> list[SecondaryDataSample]:
        """
        Load up to 100 secondary samples.
        """
        params: _PayloadType = {
            "channels": list(channels),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "limit": limit
        }
        r = self._client._http_request(
            f'{self._path}/samples/secondary', 'GET', params=params
        )

        return _SecondarySamplelistAdapter.validate_json(r.text)

    def load_metric_samples(
        self,
        channels: Optional[Collection[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        events: Optional[Collection[str]] = None,
        project: Optional[str] = None,
        limit: int = 100
    ) -> list[MetricDataSample]:
        """
        Load up to 100 metric samples.
        """
        params: _PayloadType = {
            "limit": limit
        }
        if project is not None:
            params["project"] = project
        if channels is not None:
            params["channels"] = list(channels)
        if start_time is not None:
            params["start_time"] = start_time.isoformat()
        if end_time is not None:
            params["end_time"] = end_time.isoformat()
        if events is not None:
            params["event"] = list(events)
        r = self._client._http_request(
            f'{self._path}/samples/metric', 'GET', params=params
        )

        return _MetricSamplelistAdapter.validate_json(r.text)

    def load_metric_sample(self, channel: str, event: str) -> Optional[float]:
        """
        Load a single metric sample for a specific channel and event.
        """
        samples = self.load_metric_samples([channel], events=[event])
        return samples[0].value if samples else None

    def delete_metric_samples(self, project: str, event: str, channels: Optional[Collection[str]] = None) -> None:
        params: _PayloadType = {"project": project, "event": event}
        if channels is not None:
            params["channels"] = list(channels)
        self._client._http_request(
            f'{self._path}/samples/metric', 'DELETE', params=params
        )

    def upload_file(self, project: str, datatable: str, file: str | bytes | TextIO | BinaryIO,
                    filename: Optional[str] = None,
                    timezone: Optional[str] = None) -> None:
        if isinstance(file, str):
            ctx = open(file, 'rb')
            filename = filename or os.path.basename(file)
        else:
            ctx = nullcontext(file)  # type: ignore
            filename = filename or 'file.dat'

        params: _PayloadType = {
            "project": project,
            "datatable": datatable,
        }
        if timezone is not None:
            params["timezone"] = timezone

        with ctx as f:
            self._client._http_request(f'{self._path}/files/upload/small', 'POST',
                                       params=params,
                                       files={'file': (filename, f, 'text/csv')})

    def get_latest_samples(self, project: str, include_primary: bool = True) -> list[LatestDataSample]:
        params: _PayloadType = {
            "project": project,
            "include_primary": include_primary
        }
        r = self._client._http_request(
            f'{self._path}/statistics/latest-samples', 'GET', params=params
        )

        return _LatestSampleListAdapter.validate_json(r.text)
