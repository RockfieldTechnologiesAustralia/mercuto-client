import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.notifications import (ContactGroup, ContactMethod,
                                     MercutoNotificationService,
                                     NotificationAttachment)
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)


class IssuedNotification(BaseModel):
    contact_group: ContactGroup
    subject: str
    html: str
    alternative_plaintext: Optional[str] = None
    attachments: Optional[list[NotificationAttachment]] = None
    unsubscribe_placeholder_text: Optional[str] = None

    issued_on: datetime


class MockMercutoNotificationService(MercutoNotificationService, metaclass=EnforceOverridesMeta):
    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client)
        self.contact_groups: dict[str, ContactGroup] = {}
        self.issued_notifications: list[IssuedNotification] = []

    def list_contact_groups(self) -> list[ContactGroup]:
        return list(self.contact_groups.values())

    def get_contact_group(self, code: str) -> ContactGroup:
        if code not in self.contact_groups:
            raise MercutoHTTPException(
                f"Contact group with code {code} not found", 404)
        return self.contact_groups[code]

    def create_contact_group(self, project: str, label: str, users: dict[str, list[ContactMethod]]) -> ContactGroup:
        code = str(uuid.uuid4())
        contact_group = ContactGroup(
            code=code, project=project, label=label, users=users)
        self.contact_groups[code] = contact_group
        return contact_group

    def issue_notification(self, contact_group: str, subject: str, html: str,
                           alternative_plaintext: Optional[str] = None,
                           attachments: Optional[list[NotificationAttachment]] = None,
                           unsubscribe_placeholder_text: Optional[str] = None) -> None:
        group = self.get_contact_group(contact_group)
        issued_notification = IssuedNotification(
            contact_group=group,
            subject=subject,
            html=html,
            alternative_plaintext=alternative_plaintext,
            attachments=attachments,
            unsubscribe_placeholder_text=unsubscribe_placeholder_text,
            issued_on=datetime.now(timezone.utc)
        )
        self.issued_notifications.append(issued_notification)
