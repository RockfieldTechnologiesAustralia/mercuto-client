from typing import TYPE_CHECKING, Literal, Optional

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from ._util import BaseModel

ContactMethod = Literal['EMAIL', 'SMS']


class ContactGroup(BaseModel):
    code: str
    project: str
    label: str
    users: dict[str, list[ContactMethod]]


class NotificationAttachment(BaseModel):
    """
    Attachment to include in the notification.
    """
    filename: str
    presigned_url: str  # Presigned URL to fetch the attachment from.
    mime_type: str


class Healthcheck(BaseModel):
    status: str


# --- TypeAdapters for lists ---
_ContactGroupListAdapter = TypeAdapter(list[ContactGroup])


class MercutoNotificationService:
    def __init__(self, client: 'MercutoClient', path: str = '/notifications') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    def list_contact_groups(self) -> list[ContactGroup]:
        r = self._client.request(f"{self._path}/contact-groups", "GET")
        return _ContactGroupListAdapter.validate_json(r.text)

    def get_contact_group(self, code: str) -> ContactGroup:
        r = self._client.request(f"{self._path}/contact-groups/{code}", "GET")
        return ContactGroup.model_validate_json(r.text)

    def create_contact_group(self, project: str, label: str, users: dict[str, list[ContactMethod]]) -> ContactGroup:
        r = self._client.request(f"{self._path}/contact-groups", "PUT", json={
            "project": project,
            "label": label,
            "users": users
        })
        return ContactGroup.model_validate_json(r.text)

    def issue_notification(self, contact_group: str, subject: str, html: str,
                           alternative_plaintext: Optional[str] = None,
                           attachments: Optional[list[NotificationAttachment]] = None,
                           unsubscribe_placeholder_text: Optional[str] = None) -> None:
        """
        Issue a notification to all contacts within a contact group, based on their contact preferences.

        :param contact_group: The code of the contact group to send the notification to.
        :param subject: The subject of the notification (i.e. email subject line).
        :param html: The HTML content of the notification.
        :param alternative_plaintext: Optional plaintext alternative for the notification.
            Alternative plaintext is used for SMS notifications and for email clients that do not support HTML.
        :param attachments: Optional list of attachments to include in the notification.
            Only applicable for email notifications.
        :param unsubscribe_placeholder_text: Optional placeholder text for unsubscribe links.
            Any text matching this placeholder will be replaced with an unsubscribe link for email notifications.
        :return: None
        """

        self._client.request(f"{self._path}/contact-groups/{contact_group}/issue", "POST", json={
            "subject": subject,
            "html": html,
            "alternative_plaintext": alternative_plaintext,
            "attachments": [attachment.model_dump() for attachment in attachments] if attachments else [],
            "unsubscribe_placeholder_text": unsubscribe_placeholder_text
        })
        return
