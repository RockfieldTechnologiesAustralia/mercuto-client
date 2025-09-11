import base64
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import BinaryIO, Collection, Optional, TextIO

import pandas as pd

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.data import (AggregationOptions, Channel, ChannelClassification,
                            ChannelFormat, Datatable, DatatableColumn,
                            FileFormat, FrameFormat, GetStatusRequestResponse,
                            LatestDataSample, MercutoDataService,
                            MetricDataSample, SecondaryDataSample)
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)


class MockMercutoDataService(MercutoDataService, metaclass=EnforceOverridesMeta):
    __exclude_enforce__ = {MercutoDataService.load_presigned_url,
                           MercutoDataService.load_metric_sample,
                           MercutoDataService.load_data_request}

    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client, path='/mock-data-service-method-not-implemented')
        self._secondary_and_primary_buffer = pd.DataFrame(columns=['channel', 'timestamp', 'value']).set_index(['channel', 'timestamp'])
        self._metric_buffer = pd.DataFrame(columns=['channel', 'timestamp', 'value', 'event']).set_index(['channel', 'timestamp'])

        self._known_requests: dict[str, GetStatusRequestResponse] = {}

        self._channels: dict[str, Channel] = {}
        self._datatables: dict[str, Datatable] = {}

    def _last_timestamp(self, channel: str) -> Optional[datetime]:
        if channel in self._secondary_and_primary_buffer.index.get_level_values('channel'):
            return self._secondary_and_primary_buffer.loc[channel, :].index.get_level_values('timestamp').max()
        if channel in self._metric_buffer.index.get_level_values('channel'):
            return self._metric_buffer.loc[channel, :].index.get_level_values('timestamp').max()
        return None

    def _update_last_valid_samples(self) -> None:
        for channel in self._channels.values():
            channel.last_valid_timestamp = self._last_timestamp(channel.code)

    def list_channels(self,
                      project: str,
                      classification: Optional[ChannelClassification] = None,
                      aggregate: Optional[str] = None, metric: Optional[str] = None,
                      show_hidden: bool = False) -> list[Channel]:
        selection = filter(lambda ch: ch.project == project, self._channels.values())
        if classification is not None:
            selection = filter(lambda ch: ch.classification == classification, selection)
        if aggregate is not None:
            selection = filter(lambda ch: ch.aggregate == aggregate, selection)
        if metric is not None:
            selection = filter(lambda ch: ch.metric == metric, selection)
        return list(selection)

    def get_channel(self, code: str) -> Optional[Channel]:
        return self._channels.get(code)

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

        if multiplier != 1.0:
            logger.warning("MockMercutoDataService does not support channel multiplier.")
        if offset != 0.0:
            logger.warning("MockMercutoDataService does not support channel offset.")
        if value_range_min is not None:
            logger.warning("MockMercutoDataService does not support channel value_range_min.")
        if value_range_max is not None:
            logger.warning("MockMercutoDataService does not support channel value_range_max.")
        if delta_max is not None:
            logger.warning("MockMercutoDataService does not support channel delta_max.")
        if units is not None:
            logger.warning("MockMercutoDataService does not support channel units.")

        # Generate a unique UUID code
        code = str(uuid.uuid4())
        channel = Channel(code=code,
                          project=project,
                          units=None,
                          sampling_period=sampling_period,
                          classification=classification,
                          label=label,
                          metric=metric,
                          source=source,
                          aggregate=aggregate,
                          value_range_min=None,
                          value_range_max=None,
                          multiplier=multiplier,
                          offset=offset,
                          last_valid_timestamp=None,
                          is_wallclock_interval=False)
        self._channels[code] = channel

        return channel

    def create_request(self,
                       start_time: datetime,
                       end_time: datetime,
                       project: Optional[str] = None,
                       channels: Optional[Collection[str]] = None,
                       classification: Optional[ChannelClassification] = None,
                       frame_format: FrameFormat = FrameFormat.SAMPLES,
                       file_format: FileFormat = FileFormat.PARQUET,
                       channel_format: ChannelFormat = ChannelFormat.CODE,
                       aggregation: Optional[AggregationOptions] = None,
                       timeout: float = 0) -> GetStatusRequestResponse:

        if channel_format != ChannelFormat.CODE:
            raise NotImplementedError(f"Unsupported channel format: {channel_format}")

        if channels is None and project is None:
            raise ValueError("Must supply either channels or project.")

        if channels is None and classification is None:
            raise ValueError("Must supply either channels or classification.")

        if aggregation is not None:
            raise NotImplementedError("MockMercutoDataService does not support aggregation.")

        if channels is None:
            assert classification is not None
            assert project is not None
            channels = [ch.code for ch in self._channels.values() if ch.classification == classification and ch.project == project]

        assert channels is not None

        def load_from_buffer(buffer: pd.DataFrame) -> pd.DataFrame:
            # Filter by channels if provided
            if channels is not None:
                buffer = buffer[buffer.index.get_level_values('channel').isin(channels)]

            # Filter by time range
            buffer = buffer[
                (buffer.index.get_level_values('timestamp') >= start_time) &
                (buffer.index.get_level_values('timestamp') <= end_time)
            ]
            return buffer

        secondary_part = load_from_buffer(self._secondary_and_primary_buffer)
        metric_part = load_from_buffer(self._metric_buffer)[['value']]
        ts = pd.concat([secondary_part, metric_part], axis=0).sort_index()

        assert ts.columns == ['value']
        assert ts.index.names == ['channel', 'timestamp']

        if frame_format == FrameFormat.COLUMNS:
            ts = ts.reset_index(drop=False).pivot(index='timestamp',
                                                  columns='channel',
                                                  values='value')

        buffer = io.BytesIO()
        if file_format == FileFormat.FEATHER:
            ts.to_feather(buffer)
            mime_type = 'application/feather'
        elif file_format == FileFormat.PARQUET:
            ts.to_parquet(buffer, index=True)
            mime_type = 'application/parquet'
        else:
            raise NotImplementedError(f"Unsupported file format: {file_format}")
        buffer.seek(0)
        data = buffer.read()

        first_timestamp = None if len(ts) == 0 else ts.index.get_level_values('timestamp').min()

        # Encode as a data-url
        b64_data = base64.b64encode(data).decode('utf-8')
        url = f"data:{mime_type};base64,{b64_data}"

        req = GetStatusRequestResponse(
            request_id=str(uuid.uuid4()),
            status_code=200,
            message="Success",
            requested_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            result=GetStatusRequestResponse.GetDataRequestStatusCompletedResult(
                result_url=url,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                mime_type=mime_type,
                file_size=len(data),
                metadata=GetStatusRequestResponse.GetDataRequestStatusCompletedResult.ResultMetadata(
                    first_timestamp=first_timestamp
                )
            )
        )
        self._known_requests[req.request_id] = req
        return req

    def get_request_status(self, request_id: str) -> GetStatusRequestResponse:
        if request_id not in self._known_requests:
            raise MercutoHTTPException(status_code=404, message="Not Found")
        return self._known_requests[request_id]

    def insert_metric_samples(
        self,
        project: str,
        samples: Collection[MetricDataSample]
    ) -> None:
        if not samples:
            return

        # Ensure all channels are of type METRIC
        if not all(
            sample.channel in self._channels and (self._channels[sample.channel].classification == ChannelClassification.EVENT_METRIC or
                                                  self._channels[sample.channel].classification == ChannelClassification.PRIMARY_EVENT_AGGREGATE)
            and self._channels[sample.channel].project == project
            for sample in samples
        ):
            return

        df = pd.DataFrame([{
            'channel': s.channel,
            'timestamp': s.timestamp,
            'value': s.value,
            'event': s.event
        } for s in samples])
        df = df.set_index(['channel', 'timestamp'])

        to_concat: list[pd.DataFrame] = []
        if len(self._metric_buffer) > 0:
            to_concat.append(self._metric_buffer)
        if len(df) > 0:
            to_concat.append(df)

        self._metric_buffer = pd.concat(to_concat).sort_index()
        self._update_last_valid_samples()

    def insert_secondary_samples(
        self,
        project: str,
        samples: Collection[SecondaryDataSample]
    ) -> None:
        if not samples:
            return

        # Ensure all channels are of type SECONDARY
        if not all(
            sample.channel in self._channels and self._channels[sample.channel].classification == ChannelClassification.SECONDARY
            and self._channels[sample.channel].project == project
            for sample in samples
        ):
            return

        df = pd.DataFrame([{
            'channel': s.channel,
            'timestamp': s.timestamp,
            'value': s.value,
        } for s in samples])
        df = df.set_index(['channel', 'timestamp'])

        to_concat: list[pd.DataFrame] = []
        if len(self._secondary_and_primary_buffer) > 0:
            to_concat.append(self._secondary_and_primary_buffer)
        if len(df) > 0:
            to_concat.append(df)

        self._secondary_and_primary_buffer = pd.concat(to_concat).sort_index()
        self._update_last_valid_samples()

    def delete_metric_samples(self, project: str, event: str, channels: Optional[Collection[str]] = None) -> None:
        if channels is None:
            channels = [c.code for c in self._channels.values() if c.project == project]
        idx = self._metric_buffer.index

        mask = (
            idx.get_level_values('channel').isin(channels) &
            (self._metric_buffer['event'] == event)
        )
        self._metric_buffer = self._metric_buffer[~mask]
        self._update_last_valid_samples()

    def load_metric_samples(
        self,
        channels: Optional[Collection[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        events: Optional[Collection[str]] = None,
        project: Optional[str] = None,
        limit: int = 100
    ) -> list[MetricDataSample]:
        if channels is None and project is None:
            raise ValueError("Must supply either channels or project.")

        if channels is None:
            channels = [c.code for c in self._channels.values() if c.project == project and c.classification in {
                ChannelClassification.EVENT_METRIC, ChannelClassification.PRIMARY_EVENT_AGGREGATE
            }]

        # Ensure all channels exist are of type METRIC or PRIMARY_EVENT_AGGREGATE
        if not all(
            ch in self._channels and self._channels[ch].classification in {
                ChannelClassification.EVENT_METRIC, ChannelClassification.PRIMARY_EVENT_AGGREGATE}
            for ch in channels
        ):
            return []

        idx = self._metric_buffer.index
        mask = (
            idx.get_level_values('channel').isin(channels) &
            (start_time is None or idx.get_level_values('timestamp') >= start_time) &
            (end_time is None or idx.get_level_values('timestamp') <= end_time) &
            (events is None or self._metric_buffer['event'].isin(events))
        )
        filtered = self._metric_buffer[mask]
        return [
            MetricDataSample(
                channel=channel,
                timestamp=timestamp,
                value=row['value'],
                event=row['event']
            )
            for (channel, timestamp), row in filtered.iterrows()
        ][:limit]

    def create_datatable(self, project: str, name: str, sampling_period: timedelta, column_labels: Collection[str]) -> Datatable:
        if sampling_period <= timedelta(seconds=1):
            classification = ChannelClassification.PRIMARY
        else:
            classification = ChannelClassification.SECONDARY
        channels = [self.create_channel(project=project, label=col, classification=classification,
                                        sampling_period=sampling_period) for col in column_labels]
        dt = Datatable(
            code=str(uuid.uuid4()),
            project=project,
            name=name,
            sampling_period=sampling_period,
            columns=[DatatableColumn(column_label=ch.label, channel=ch.code) for ch in channels],
            enabled=True
        )
        self._datatables[dt.code] = dt
        return dt

    def _dt_col_to_channel_code(self, dt: str, column_label: str) -> str:
        for col in self._datatables[dt].columns:
            if col.column_label == column_label:
                return col.channel
        raise ValueError(f"Column label '{column_label}' not found in datatable '{dt}'")

    def upload_file(self, project: str, datatable: str, file: str | bytes | TextIO | BinaryIO,
                    filename: Optional[str] = None,
                    timezone: Optional[str] = None) -> None:
        frame = pd.read_csv(file, header=1, skiprows=[2, 3],
                            usecols=None, sep=',', index_col=0, na_values=['NAN', '"NAN"'])
        frame.index = pd.to_datetime(frame.index, utc=False)
        assert isinstance(frame.index, pd.DatetimeIndex)
        if frame.index.tz is None:
            frame.index = frame.index.tz_convert(timezone)
        del frame['RECORD']

        # Drop unknown channels
        frame = frame[[col for col in frame.columns if col in {c.column_label for c in self._datatables[datatable].columns}]]

        # rename from label to code
        frame = frame.rename(columns=lambda x: self._dt_col_to_channel_code(datatable, x))

        frame = frame.melt([], tuple(frame.columns), ignore_index=False, var_name='channel',
                           value_name='value').sort_index()
        frame.index.name = 'timestamp'
        frame = frame.reset_index().set_index(['channel', 'timestamp'])
        self._secondary_and_primary_buffer = pd.concat([self._secondary_and_primary_buffer, frame]).sort_index()
        self._update_last_valid_samples()

    def get_latest_samples(self, project: str, include_primary: bool = True) -> list[LatestDataSample]:
        if include_primary:
            channels = [c.code for c in self._channels.values() if c.project == project]
        else:
            channels = [ch for ch in channels if self._channels[ch].classification !=
                        ChannelClassification.PRIMARY and self._channels[ch].project == project]

        out: list[LatestDataSample] = []

        # Get the last timestamp and value for each channel in the secondary_and_primary_buffer
        latest = self._secondary_and_primary_buffer.groupby(level='channel').last()
        for (channel, timestamp), row in latest.iterrows():
            if channel not in channels:
                continue
            out.append(LatestDataSample(channel=channel,
                                        timestamp=timestamp,
                                        value=row['value']))

        latest = self._metric_buffer.groupby(level='channel').last()
        for (channel, timestamp), row in latest.iterrows():
            if channel not in channels:
                continue
            out.append(LatestDataSample(channel=channel,
                                        timestamp=timestamp,
                                        value=row['value']))
        return out
