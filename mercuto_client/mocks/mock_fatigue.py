import logging
from datetime import datetime
from typing import Literal, Optional

from ..client import MercutoClient
from ..modules.fatigue import MercutoFatigueService
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)


class MockMercutoFatigueService(MercutoFatigueService, metaclass=EnforceOverridesMeta):
    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client, path='/mock-fatigue-service-method-not-implemented')

    def delete_cycle_counts(
        self, project: str, start_time: datetime, end_time: datetime, ignore_if_not_configured: bool = False
    ) -> None:
        pass

    def calculate_cycle_counts(
        self,
        project: str,
        event: str,
        presigned_url: str,
        mime_type: Literal['application/feather'],
        url_expiry: Optional[datetime] = None,
        ignore_if_not_configured: bool = False
    ) -> None:
        pass
