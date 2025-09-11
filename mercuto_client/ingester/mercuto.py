import fnmatch
import logging
import os
from typing import Optional

from .. import MercutoClient, MercutoHTTPException
from ..modules.core import Project
from ..modules.data import (Channel, ChannelClassification, Datatable,
                            SecondaryDataSample)
from ..util import batched, get_my_public_ip
from .parsers import detect_parser

logger = logging.getLogger(__name__)

NON_RETRYABLE_ERRORS = {400, 404, 409}  # HTTP status codes that indicate non-retryable errors


class MercutoIngester:
    def __init__(self, project_code: str, api_key: str, hostname: str = 'https://api.rockfieldcloud.com.au') -> None:
        self._client = MercutoClient(url=hostname)
        self._api_key = api_key
        self._project_code = project_code

        self._project: Optional[Project] = None
        self._secondary_channels: Optional[list[Channel]] = None
        self._datatables: Optional[list[Datatable]] = None

        self._channel_map: dict[str, str] = {}

    def _refresh_mercuto_data(self) -> None:
        with self._client.as_credentials(api_key=self._api_key) as client:
            self._project = client.core().get_project(self._project_code)
            assert self._project.code == self._project_code

            self._secondary_channels = client.data().list_channels(self._project_code, classification=ChannelClassification.SECONDARY)
            self._datatables = client.data().list_datatables(self._project_code)

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
        logging.info(f"Uploadeding file {file_path} to datatable {datatable_code} in project {self.project_code}")
        try:
            with self._client.as_credentials(api_key=self._api_key) as client:
                client.data().upload_file(
                    project=self.project_code,
                    datatable=datatable_code,
                    file=file_path,
                )
            return True
        except MercutoHTTPException as e:
            if e.status_code in NON_RETRYABLE_ERRORS:
                logger.exception(
                    "Error indicates bad file that should not be retried. Skipping.")
                return True
            else:
                return False

    def process_file(self, file_path: str) -> bool:
        """
        Process the received file.
        """

        if not self._can_process():
            logging.info("Refreshing Mercuto data...")
            self._refresh_mercuto_data()
            if not self._can_process():
                logging.error("Failed to refresh Mercuto data. Cannot process file yet.")
                return False

        logging.info(f"Processing file: {file_path}")
        datatable_code = self.matching_datatable(file_path)
        if datatable_code:
            logger.info(f"Matched datatable code: {datatable_code} for file: {file_path}")
            return self._upload_file(file_path, datatable_code)
        else:
            parser = detect_parser(file_path)
            samples = parser(file_path, self._channel_map)
            if not samples:
                logging.warning(f"No samples found in file: {file_path}")
                return True
            return self._upload_samples(samples)
