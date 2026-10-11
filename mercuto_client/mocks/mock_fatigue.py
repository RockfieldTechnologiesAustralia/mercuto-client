import logging

from ..client import MercutoClient
from ..modules.fatigue import MercutoFatigueService
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)


class MockMercutoFatigueService(MercutoFatigueService, metaclass=EnforceOverridesMeta):
    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client, path='/mock-fatigue-service-method-not-implemented')
