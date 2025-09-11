from .client import MercutoClient
from .exceptions import MercutoClientException, MercutoHTTPException

__all__ = ['MercutoClient', 'MercutoHTTPException', 'MercutoClientException']


def connect(*args, **kwargs) -> MercutoClient:
    return MercutoClient().connect(*args, **kwargs)
