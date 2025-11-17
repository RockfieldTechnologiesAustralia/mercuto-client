from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional, Protocol, TypedDict

from pydantic import TypeAdapter

from . import PayloadType
from ._util import BaseModel

if TYPE_CHECKING:
    from ..client import MercutoClient


class ScheduledReport(BaseModel):
    code: str
    project: str
    label: str
    revision: str
    schedule: Optional[str]
    contact_group: Optional[str]
    last_scheduled: Optional[str]


class ScheduledReportLog(BaseModel):
    code: str
    report: str
    scheduled_start: Optional[str]
    actual_start: str
    actual_finish: Optional[str]
    status: Literal['IN_PROGRESS', 'COMPLETED', 'FAILED']
    message: Optional[str]
    access_url: Optional[str]
    mime_type: Optional[str]
    filename: Optional[str]


class ReportSourceCodeRevision(BaseModel):
    code: str
    revision_date: datetime
    description: str
    source_code_url: str


_ScheduledReportListAdapter = TypeAdapter(list[ScheduledReport])
_ScheduledReportLogListAdapter = TypeAdapter(list[ScheduledReportLog])

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
    tenant_code: str
    report_code: str
    log_code: str
    client: 'MercutoClient'


class ReportHandler(Protocol):
    def __call__(self,
                 request: 'HandlerRequest',
                 context: 'HandlerContext') -> 'ReportHandlerResultLike':
        ...


class MercutoReportService:
    def __init__(self, client: 'MercutoClient') -> None:
        self._client = client

    def list_reports(self, project: Optional[str] = None) -> list['ScheduledReport']:
        """
        List scheduled reports, optionally filtered by project.
        """
        params: PayloadType = {}
        if project is not None:
            params['project'] = project
        r = self._client.request(
            '/reports/scheduled', 'GET', params=params)
        return _ScheduledReportListAdapter.validate_json(r.text)

    def create_report(self, project: str, label: str, schedule: str, revision: str,
                      contact_group: Optional[str] = None) -> ScheduledReport:
        """
        Create a new scheduled report using the provided source code revision.
        """
        json: PayloadType = {
            'project': project,
            'label': label,
            'schedule': schedule,
            'revision': revision,
            'contact_group': contact_group
        }
        r = self._client.request('/reports/scheduled', 'PUT', json=json)
        return ScheduledReport.model_validate_json(r.text)

    def generate_report(self, report: str, timestamp: datetime, mark_as_scheduled: bool = False) -> ScheduledReportLog:
        """
        Trigger generation of a scheduled report for a specific timestamp.
        """
        r = self._client.request(f'/reports/scheduled/{report}/generate', 'PUT', json={
            'timestamp': timestamp.isoformat(),
            'mark_as_scheduled': mark_as_scheduled
        })
        return ScheduledReportLog.model_validate_json(r.text)

    def list_report_logs(self, report: str, project: Optional[str] = None) -> list[ScheduledReportLog]:
        """
        List report log entries for a specific report.
        """
        params: PayloadType = {}
        if project is not None:
            params['project'] = project
        r = self._client.request(
            f'/reports/scheduled/{report}/logs', 'GET', params=params)
        return _ScheduledReportLogListAdapter.validate_json(r.text)

    def get_report_log(self, report: str, log: str) -> ScheduledReportLog:
        """
        Get a specific report log entry.
        """
        r = self._client.request(
            f'/reports/scheduled/{report}/logs/{log}', 'GET')
        return ScheduledReportLog.model_validate_json(r.text)

    def create_report_revision(self, project: str, revision_date: datetime,
                               description: str, source_code_data_url: str) -> ReportSourceCodeRevision:
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
            source_code_data_url (str): A presigned URL to the report source code file, either a .py file or a .zip package.

        """
        json = {
            'revision_date': revision_date.isoformat(),
            'description': description,
            'source_code_data_url': source_code_data_url,
        }
        r = self._client.request(
            '/reports/revisions', 'PUT', json=json, params={'project': project})
        return ReportSourceCodeRevision.model_validate_json(r.text)
