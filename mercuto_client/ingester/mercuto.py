import fnmatch
import logging
import os
from datetime import datetime
from typing import Optional

import pytz

from .. import MercutoClient, MercutoHTTPException
from ..modules.core import Project
from ..modules.data import (Channel, ChannelClassification, Datatable,
                            SecondaryDataSample)
from ..modules.media import Camera
from ..util import batched, get_my_public_ip
from .parsers import detect_parser

logger = logging.getLogger(__name__)

NON_RETRYABLE_ERRORS = {400, 404, 409}  # HTTP status codes that indicate non-retryable errors


def _get_file_mtime(file_path: str, increment: int) -> datetime:
    """
    Returns the file modification time rounded down to the nearest increment.
    """
    ts = os.path.getmtime(file_path)
    ts = ts - (ts % increment)
    return datetime.fromtimestamp(ts).astimezone()


class MercutoIngester:
    def __init__(self, project_code: str, api_key: str,
                 hostname: str = 'https://api.rockfieldcloud.com.au',
                 verify_ssl: bool = True,
                 timezone: Optional[str] = None,
                 camera_code: Optional[str] = None) -> None:
        """
        :param project_code: The Mercuto project code to ingest data into.
        :param api_key: The API key to use for authentication.
        :param hostname: The Mercuto server hostname.
        :param verify_ssl: Verify SSL certificates for the target server when using https. Default True.
        :param timezone: The timezone to use for data uploads as a string (e.g. 'Australia/Melbourne').
        :param camera_code: Optional camera code to associate with image uploads. If not provided, image uploads will error.
        """
        self._client = MercutoClient(url=hostname, verify_ssl=verify_ssl)
        self._api_key = api_key
        self._project_code = project_code
        self._timezone = timezone
        self._timezone_tzinfo = pytz.timezone(timezone) if timezone else None
        self._camera_code = camera_code

        self._project: Optional[Project] = None
        self._secondary_channels: Optional[list[Channel]] = None
        self._datatables: Optional[list[Datatable]] = None
        self._camera: Optional[Camera] = None

        self._channel_map: dict[str, str] = {}

    def _refresh_mercuto_data(self) -> None:
        with self._client.as_credentials(api_key=self._api_key) as client:
            self._project = client.core().get_project(self._project_code)
            assert self._project.code == self._project_code

            self._secondary_channels = client.data().list_channels(self._project_code, classification=ChannelClassification.SECONDARY)
            self._datatables = client.data().list_datatables(self._project_code)
            if self._camera_code is not None:
                self._camera = client.media().get_camera(self._camera_code)

        self._channel_map.update({c.label: c.code for c in self._secondary_channels})

    def _can_process(self) -> bool:
        return self._project is not None and self._secondary_channels is not None and self._datatables is not None

    def update_mapping(self, mapping: dict[str, str]) -> None:
        """
        Update the channel label to channel code mapping.
        """
        self._channel_map.update(mapping)
        logger.info(f"Updated channel mapping: {self._channel_map}")

    @property
    def project_code(self) -> str:
        return self._project_code

    def ping(self) -> None:
        """
        Ping the Mercuto serverto update the last seen IP address.
        """
        ip = get_my_public_ip()
        with self._client.as_credentials(api_key=self._api_key) as client:
            client.core().ping_project(self.project_code, ip_address=ip)
            logging.info(f"Pinged Mercuto server from IP: {ip} for project: {self.project_code}")

    def matching_datatable(self, filename: str) -> str | None:
        """
        Check if any datatables on the project match this file name.
        Returns the datatable code if a match is found, otherwise None.
        """
        if self._datatables is None:
            raise ValueError("Datatables not loaded. Call _refresh_mercuto_data() first.")

        basename = os.path.basename(filename)

        def matches(test: str) -> bool:
            """
            test should be a pattern or a filename.
            E.g. "my_data.csv" or "my_data*.csv", or "/path/to/my_data*.csv"
            Do wildcard matching as well as prefix matching.
            """
            test_base = os.path.basename(test)
            if fnmatch.fnmatch(basename, test_base):
                return True
            lhs, _ = os.path.splitext(test_base)
            if basename.startswith(lhs):
                return True
            return False

        for dt in self._datatables:
            # Match using datatable pattern
            if matches(dt.name):
                return dt.code
        return None

    def _upload_samples(self, samples: list[SecondaryDataSample]) -> bool:
        """
        Upload samples to the Mercuto project.
        """
        try:
            with self._client.as_credentials(api_key=self._api_key) as client:
                for batch in batched(samples, 500):
                    client.data().insert_secondary_samples(self.project_code, batch)
            return True
        except MercutoHTTPException as e:
            logger.error(f"Failed to upload samples: {e}")
            if e.status_code in NON_RETRYABLE_ERRORS:
                logger.exception(
                    "Error indicates bad file that should not be retried. Skipping.")
                return True
            else:
                return False

    def _upload_file(self, file_path: str, datatable_code: str) -> bool:
        """
        Upload a file to the Mercuto project.
        """
        logging.info(f"Uploading file {file_path} to datatable {datatable_code} in project {self.project_code}")
        try:
            with self._client.as_credentials(api_key=self._api_key) as client:
                client.data().upload_file(
                    project=self.project_code,
                    datatable=datatable_code,
                    file=file_path,
                    timezone=self._timezone
                )
            return True
        except MercutoHTTPException as e:
            logger.error(f"Failed to upload file {file_path} to datatable {datatable_code}: {e}")
            if e.status_code in NON_RETRYABLE_ERRORS:
                logger.exception(
                    "Error indicates bad file that should not be retried. Skipping.")
                return True
            else:
                return False

    def process_file(self, file_path: str) -> bool:
        """
        Process the received file.
        Returns True if processed successfully or should not be retried, False if processing failed and should be retried.
        """

        if not self._can_process():
            logging.info("Refreshing Mercuto data...")
            self._refresh_mercuto_data()
            if not self._can_process():
                logging.error("Failed to refresh Mercuto data. Cannot process file yet.")
                return False

        logging.info(f"Processing file: {file_path}")

        ext = os.path.splitext(file_path)[1]
        if ext in ['.dat', '.csv']:
            return self._process_data_file(file_path)
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
            return self._process_image_file(file_path)
        else:
            logger.error(f"Unsupported file extension: {ext} for file: {file_path}")
            # We mark unsupported files as processed to avoid retrying
            return True

    def _process_data_file(self, file_path: str) -> bool:
        """
        Process a data file specifically.
        Supported extensions: .dat, .csv
        """
        assert file_path.endswith(('.dat', '.csv'))
        datatable_code = self.matching_datatable(file_path)
        if datatable_code:
            logger.info(f"Matched datatable code: {datatable_code} for file: {file_path}")
            return self._upload_file(file_path, datatable_code)
        else:
            parser = detect_parser(file_path)
            samples = parser(file_path, self._channel_map, timezone=self._timezone_tzinfo)
            if not samples:
                logging.warning(f"No samples found in file: {file_path}")
                return True
            return self._upload_samples(samples)

    def _process_image_file(self, file_path: str) -> bool:
        """
        Process an image file specifically.
        For .jpg, .png, etc.
        """
        assert file_path.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff'))
        if self._camera is None:
            logger.error("No camera specified for image upload. Cannot process image file.")
            return False

        logging.info(f"Uploading image file {file_path} to camera {self._camera.code} in project {self.project_code}")
        timestamp = _get_file_mtime(file_path, increment=1)

        try:
            with self._client.as_credentials(api_key=self._api_key) as client:
                client.media().upload_image(
                    filename=file_path,
                    project=self.project_code,
                    camera=self._camera.code,
                    timestamp=timestamp,
                    event=None,
                    filedata=None
                )
            return True
        except MercutoHTTPException as e:
            logger.error(f"Failed to upload image file {file_path} to camera {self._camera.code}: {e}")
            if e.status_code in NON_RETRYABLE_ERRORS:
                logger.exception(
                    "Error indicates bad file that should not be retried. Skipping.")
                return True
            else:
                return False
