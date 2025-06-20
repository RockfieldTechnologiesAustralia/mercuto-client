import time
from datetime import datetime, timezone
from typing import List, Literal, Optional, TypedDict

import matplotlib.pyplot as plt
import pandas as pd
import requests

"""
Global configuration used for these examples.
"""

API_KEY = "<YOUR API KEY HERE>"  # API Key for Rockfield's API.
API_URL = "https://api.rockfieldcloud.com.au"
PROJECT_CODE = "12345678"  # Project code


"""
Here we are defining some common types that are returned by Rockfield's API. These types are not an exhaustive list, just
some of the more common ones that are used in the examples below.
"""


class DataRequestResponse(TypedDict):
    code: str  # Unique token to identify this request.
    requested_at: str  # Time that the request was made. (ISO8601 formatted datetime)
    completed_at: Optional[str]  # Time that the request was resolved. null if in progress still. ISO8601 formatted datetime.
    in_progress: bool  # True if the request is being processed still. False if the request is complete.
    presigned_url: Optional[str]  # Unique URL to access the completed data in CSV format, once ready.
    message: Optional[str]  # Any messages associated with the request. E.g. reasons for failure.
    mime_type: str  # Mime type of the data file. Typically 'text/csv'


class CodeField(TypedDict):
    code: str


class SensorUnits(TypedDict):
    name: str  # E.g. Microstrain
    unit: Optional[str]  # E.g. µε


class DeviceType(TypedDict):
    description: str
    manufacturer: str
    device_model_number: str


class Device(TypedDict):
    code: str
    label: str
    location_description: str
    device_type: DeviceType


class SensorChannel(TypedDict):
    code: str
    label: str
    units: Optional[SensorUnits]  # Units for data received on this channel. Null if not set.
    sampling_period: Optional[str]  # Interval that regular data is captured at for this channel. ISO8601 formatted duration string.
    classification: Literal['PRIMARY', 'SECONDARY', 'PRIMARY_EVENT_AGGREGATE', 'EVENT_METRIC']  # Channel type classification.
    device: Optional[CodeField]  # Device code that the channel is attached to. (For PRIMARY and SECONDARY channels only)
    metric: Optional[str]  # The metric name of this channel (can be thought of as the sub-field within either source or device)
    source: Optional[CodeField]  # The primary channel this channel is sourced from. (For PRIMARY_EVENT_AGGREGATE channels only)
    aggregate: Optional[str]  # Aggregate type. (For PRIMARY_EVENT_AGGREGATE channels only)


class DataEventMetric(TypedDict):
    channel: SensorChannel
    value: float


class DataEventTag(TypedDict):
    tag: str
    value: str


class DataEventObject(TypedDict):
    code: str  # Unique object identifier
    mime_type: str  # Object's internal MIME type (i.e. image/jpeg)
    size_bytes: int  # Size of the object in bytes.
    name: str  # Original object filename.

    access_url: str  # Unique URL used to access the object.
    access_expires: str  # Time at which the unique URL becomes invalid (ISO8601 formatted datetime).


class DataEvent(TypedDict):
    code: str  # Unique identifier for the event
    start_time: str  # ISO8601 formatted start time of the event
    end_time: str  # ISO8601 formatted end time of the event

    objects: List[DataEventObject]  # List of objects that were involved in the event
    metrics: List[DataEventMetric]  # List of metrics that were involved in the event
    tags: List[DataEventTag]  # List of tags that were involved in the event


def example1_find_event_by_timestamp(timestamp: datetime) -> DataEvent:
    """
    Example 1: Finding an event that occurred at a specific time, within a 1 minute window.

    @param timestamp: The timestamp of the event we want to find.
                        If no timezone is provided, then `project timezone` is assumed (UTC typically).

    @returns: Details of the event. If no event is found, returns None.
    """
    response = requests.get(API_URL + "/events/nearest", headers={
        'X-API-Key': API_KEY
    }, params={
        'project_code': PROJECT_CODE,
        'to': timestamp.isoformat(),
        'maximum_delta': "P1M",  # ISO8601 formatted duration string. P1M = 1 month
    })
    response.raise_for_status()
    return response.json()


def example2_load_waveform_for_event(event_code: str) -> pd.DataFrame:
    """
    Example 2: Loading the waveform data for a specific event into a pandas Dataframe.
        The column names for the dataframe will be the labels for each sensor channel
    This example will block for up to 20-seconds waiting for the data to be ready.
    """
    response = requests.post(API_URL + "/data/requests", headers={
        'X-API-Key': API_KEY
    }, params={'timeout': 20}, json={
        'project_code': PROJECT_CODE,
        'event_code': event_code,
        'primary_channels': True,  # Waveform data is only available for primary channels
    })
    response.raise_for_status()
    response_json = response.json()

    # The response contains a presigned_url that we can use to download the data for a short window of time.

    # Read the data from the presigned_url into a pandas DataFrame
    data = pd.read_csv(response_json['presigned_url'], skiprows=[
                       0, 2, 3], index_col=0, parse_dates=True)

    # Typically a 'RECORD' column is returned in the data, which is the record number of the data point.
    # This may not always be desired, so remove it from the dataframe.
    if 'RECORD' in data.columns:
        data = data.drop(columns=['RECORD'])

    data = data.dropna(axis=1, how='all').select_dtypes(include='number')

    return data


def example3_list_available_sensor_channels() -> List[SensorChannel]:
    """
    Example 3: List sensor channels that are available for querying data.
    Sensor channels are sources of timeseries data that produce numeric datapoints.

    Sensor channels are separated into four classifications:
        - PRIMARY: Channels that are directly attached to a device, and are high speed (>10Hz) sampling rate during events only, such as strain.
        - SECONDARY: Channels that are directly attached to a device, and are low speed (< 1-per minute), typically sampled 24/7, such as temperature.
        - EVENT_METRIC: Channels that are derived from an event, with one sample per event, such as vehicle-speed.
        - PRIMARY_EVENT_AGGREGATE: Channels that are derived from an event and are an aggregate of another channel, with one sample per event,
            such as MAX of strain at location A.
    """
    response = requests.get(API_URL + "/channels", headers={
        'X-API-Key': API_KEY
    }, params={
        'project_code': PROJECT_CODE,
        'limit': '500'})  # Note: Default limit is 100 channels
    response.raise_for_status()
    return response.json()


def example4_data_within_timerange_for_channel(channel: SensorChannel, start_time: datetime, end_time: datetime) -> pd.DataFrame:
    """
    Example 4: Load data for a specific sensor channel within a specific time range into a pandas DataFrame.
    The column names for the dataframe will be the labels for each sensor channel.

    This example will poll the status of the data request waiting until the data is ready. This method is useful
    if data volume requested is large and may take longer than the maximum busy-wait of 20-seconds allowed by the API.

    """
    if channel['classification'] == 'PRIMARY':
        # Primary channels are high speed and only have data during events.
        raise ValueError("Cannot load data for primary channels. Use example2_load_waveform_for_event instead.")

    response = requests.post(API_URL + "/data/requests?timeout=0", headers={
        'X-API-Key': API_KEY
    }, json={
        'project_code': PROJECT_CODE,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'channel_codes': [channel['code']]  # You can pass as many channel codes as you like here.
    })
    response.raise_for_status()
    response_json: DataRequestResponse = response.json()

    # Poll the status of the data request until it is ready.
    while True:
        print("Polling for data...")
        response = requests.get(API_URL + "/data/requests/" + response_json['code'], headers={
            'X-API-Key': API_KEY
        })
        response.raise_for_status()
        response_json = response.json()
        if not response_json['in_progress']:
            break

        # Wait a little bit before polling again.
        time.sleep(0.5)

    if response_json['presigned_url'] is None:
        raise ValueError(f"Could not load data. Reason given: {response_json['message']}")

    # Read the data from the presigned_url into a pandas DataFrame
    data = pd.read_csv(response_json['presigned_url'], skiprows=[
                       0, 2, 3], index_col=0, parse_dates=True)

    if 'RECORD' in data.columns:
        data = data.drop(columns=['RECORD'])
    data = data.dropna(axis=1, how='all').astype(float)
    return data


def example5_load_devices() -> List[Device]:
    """
    This is a helper to load all the registered devices for a project.
    A device is a physical sensor installed on site that has one or more streams of data (Sensor Channels).
    E.g. A strain gauge, producing high frequency strain, background strain, and temperature.
    """
    response = requests.get(API_URL + "/devices", headers={
        'X-API-Key': API_KEY
    }, params={'project_code': PROJECT_CODE})
    response.raise_for_status()
    return response.json()


def example6_relabel_dataframe_columns(data: pd.DataFrame, known_channels: List[SensorChannel], known_devices: List[Device]) -> pd.DataFrame:
    """
    Example 5: Data returned via the API is typically labelled with the channel label.
    This can be mapped to the device label which is a better representation of sensor description.
    """

    # We can relabel the sensor channels to use the channel's device name instead of the channel label.
    def mapper(channel_label: str) -> str:
        try:
            sensor_channel = next(iter(filter(lambda d: d['label'] == channel_label, known_channels)))
            if sensor_channel['device'] is None:
                # No device is associated with this channel, return original label.
                return channel_label
            device_code = sensor_channel['device'].get('code', None)
            device = next(iter(filter(lambda d: d['code'] == device_code, known_devices)))
            return device['label']
        except (StopIteration, IndexError):
            # Could not find matching device, return original label.
            return channel_label
    return data.rename(columns=mapper)


def example7_download_event_video(dataevent: DataEvent, path: str):
    """
    Example 7: Download a video associated with an event to the path given by 'path'.
    """
    # The dataevent object contains a list of objects that were involved in the event.
    # We can filter this list to find the video object, finding all objects with the mime_type starting with 'video/'.
    videos = list(filter(lambda obj: obj['mime_type'].startswith('video/'), dataevent['objects']))

    if len(videos) == 0:
        raise ValueError("No video objects found for event.")

    # We will download the first video object found.
    video = videos[0]
    with requests.get(video['access_url'], stream=True) as r:
        r.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


if __name__ == "__main__":
    print("Running example API usage...")
    print("Finding event by timestamp...")
    example_event = example1_find_event_by_timestamp(datetime(year=2024, month=8, day=12, hour=21, minute=31, second=16, tzinfo=timezone.utc))
    print("Loading waveform for event...")
    example_event_data = example2_load_waveform_for_event(example_event['code'])
    print("Listing available sensor channels...")
    available_sensor_channels = example3_list_available_sensor_channels()
    print(f"{len(available_sensor_channels)} channels found.")

    print("Loading devices...")
    available_devices = example5_load_devices()

    # Get the last 'greatest' channel from the full channel list
    aggregate_channel = list(filter(lambda c: c['aggregate'] == 'greatest', available_sensor_channels))[-1]

    # Load the 'greatest' data for all time into a pandas Dataframe.
    print("Loading greatest channel data...")
    example_aggregate_data = example4_data_within_timerange_for_channel(
        aggregate_channel,
        datetime(year=2024, month=1, day=1),
        datetime(year=2030, month=1, day=1))

    # Rename the event dataset columns to use the device label instead of the channel label.
    example_event_data = example6_relabel_dataframe_columns(example_event_data, available_sensor_channels, available_devices)

    # Remove some columns from the event waveform to make the plot nicer to visualize
    example_event_data = example_event_data[['VW_1', 'VW_2', 'VW_3']]

    # Plot the dataset that we loaded.
    fig, [ax1, ax2] = plt.subplots(2, 1)  # type: ignore
    example_event_data.plot(ax=ax1)
    ax1.set_title(f"Example Event Waveform for event at {example_event['start_time']}")
    ax1.set_ylabel("Microstrain (µε)")
    example_aggregate_data.plot(ax=ax2, linestyle='none', marker='.')
    ax2.set_title(f"Greatest Value Per Event for Sensor {aggregate_channel['label']}")
    ax2.set_ylabel("Microstrain (µε)")
    fig.tight_layout()

    # Download a video associated with the event.
    print("Downloading video associated with an event to file `event_video.mp4`...")
    example7_download_event_video(example_event, "event_video.mp4")

    plt.show()
