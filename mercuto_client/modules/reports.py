from datetime import datetime
from typing import (TYPE_CHECKING, BinaryIO, Literal, Optional, Protocol,
                    TypedDict)

from pydantic import AwareDatetime, TypeAdapter

from ..exceptions import MercutoHTTPException
from . import PayloadType
from ._util import BaseModel

if TYPE_CHECKING:
    from ..client import MercutoClient


class ReportConfiguration(BaseModel):
    code: str
    project: str
    label: str
    revision: str
    schedule: Optional[str] = None
    contact_group: Optional[str] = None
    last_scheduled: Optional[AwareDatetime] = None
    custom_policy: Optional[str] = None


ReportLogStatus = Literal['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED']


class ReportLog(BaseModel):
    code: str
    report_configuration: str
    scheduled_start: Optional[AwareDatetime]
    actual_start: AwareDatetime
    actual_finish: Optional[AwareDatetime]
    status: ReportLogStatus
    message: Optional[str]
    access_url: Optional[str]
    mime_type: Optional[str]
    filename: Optional[str]


class ReportSourceCodeRevision(BaseModel):
    code: str
    project: Optional[str]
    revision_date: AwareDatetime
    description: str
    source_code_url: str


class Healthcheck(BaseModel):
    status: str


_ReportConfigurationListAdapter = TypeAdapter(list[ReportConfiguration])
_ReportLogListAdapter = TypeAdapter(list[ReportLog])

"""
The below types are used for defining report generation functions.
They are provided for type-checking and helpers for users writing custom reports.
"""


class ReportHandlerResultLike(Protocol):
    filename: str
    mime_type: str
    data: bytes


class ReportHandlerResult(BaseModel):
    filename: str
    mime_type: str
    data: bytes


class HandlerRequest(TypedDict):
    timestamp: datetime


class HandlerContext(TypedDict):
    service_token: str
    project_code: str
    report_code: str
    log_code: str
    client: 'MercutoClient'


class ReportHandler(Protocol):
    def __call__(self,
                 request: 'HandlerRequest',
                 context: 'HandlerContext') -> 'ReportHandlerResultLike':
        ...


class MercutoReportService:
    def __init__(self, client: 'MercutoClient', path: str = '/reports') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    def list_report_configurations(self, project: str) -> list['ReportConfiguration']:
        """
        List scheduled reports for a specific project.
        """
        params: PayloadType = {
            'project': project
        }
        r = self._client.request(
            f'{self._path}/configurations', 'GET', params=params)
        return _ReportConfigurationListAdapter.validate_json(r.text)

    def create_report_configuration(self, project: str, label: str, schedule: str, revision: str,
                                    contact_group: Optional[str] = None, custom_policy: Optional[str] = None) -> ReportConfiguration:
        """
        Create a new scheduled report using the provided source code revision.
        """
        json: PayloadType = {
            'project': project,
            'label': label,
            'schedule': schedule,
            'revision': revision,
        }
        if contact_group is not None:
            json['contact_group'] = contact_group
        if custom_policy is not None:
            json['custom_policy'] = custom_policy
        r = self._client.request(
            f'{self._path}/configurations', 'PUT', json=json)
        return ReportConfiguration.model_validate_json(r.text)

    def generate_report(self, report: str, timestamp: datetime, mark_as_scheduled: bool = False) -> ReportLog:
        """
        Trigger generation of a scheduled report for a specific timestamp.
        """
        r = self._client.request(f'{self._path}/configurations/{report}/generate', 'POST', json={
            'timestamp': timestamp.isoformat(),
            'mark_as_scheduled': mark_as_scheduled
        })
        return ReportLog.model_validate_json(r.text)

    def list_report_logs(self, project: str, report: Optional[str] = None) -> list[ReportLog]:
        """
        List report log entries for a specific project.
        """
        params: PayloadType = {
            'project': project
        }
        if report is not None:
            params['configuration'] = report
        r = self._client.request(
            f'{self._path}/logs', 'GET', params=params)
        return _ReportLogListAdapter.validate_json(r.text)

    def get_report_log(self, log: str) -> ReportLog:
        """
        Get a specific report log entry.
        """
        r = self._client.request(
            f'{self._path}/logs/{log}', 'GET')
        return ReportLog.model_validate_json(r.text)

    def create_report_revision(self, revision_date: datetime,
                               description: str,
                               project: Optional[str],
                               source_code: BinaryIO) -> ReportSourceCodeRevision:
        """
        Create a new report source code revision.

        A report should be a python file that defines a function called `generate_report`
        that takes two arguments: `request` and `context`, and returns an object with
        `filename`, `mime_type`, and `data` attributes. It can also be a package with __init__.py
        defining the `generate_report` function.

        You can use the `mercuto_client.modules.reports.ReportHandler` protocol
        to type hint your report function. Example:
        ```python
        from mercuto_client.modules.reports import ReportHandler, HandlerRequest, HandlerContext, ReportHandlerResult
        def generate_report(request: HandlerRequest, context: HandlerContext) -> ReportHandlerResult:
            # Your report generation logic here
            return ReportHandlerResult(
                filename="report.pdf",
                mime_type="application/pdf",
                data=b"PDF binary data here"
            )
        ```
        The request parameter contains information about the report generation request,
        and the context parameter provides access to the Mercuto client and metadata about
        the report being generated. The MercutoClient provided in the context can be used
        to fetch any additional data required for the report. It will be authenticated
        using a service token with VIEW_PROJECT permission and VIEW_TENANT permission.

        Params:
            project (str): The project code.
            revision_date (datetime): The date of the revision.
            description (str): A description of the revision.
            source_code (io.BinaryIO): The report source code file, either a .py file or a .zip package.

        """
        # Create the revision metadata
        json: PayloadType = {
            'revision_date': revision_date.isoformat(),
            'description': description,
        }
        if project is not None:
            json['project'] = project
        r = self._client.request(f'{self._path}/revisions', 'PUT', json=json)
        revision = ReportSourceCodeRevision.model_validate_json(r.text)

        # Upload the source code
        r = self._client.request(
            f'{self._path}/revisions/{revision.code}', 'PATCH')
        upload_url = r.json()['target_source_code_url']
        upload_url = self._client.session().put(upload_url,
                                                data=source_code, verify=self._client.verify_ssl)
        if not upload_url.ok:
            raise MercutoHTTPException(
                f"Failed to upload report source code: {upload_url.status_code} {upload_url.text}",
                upload_url.status_code
            )
        return revision
