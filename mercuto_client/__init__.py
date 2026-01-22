from .client import MercutoClient
from .exceptions import (MercutoClientException, MercutoHTTPException,
                         MercutoNotFoundException)

__all__ = ['MercutoClient', 'MercutoHTTPException', 'MercutoClientException', 'MercutoNotFoundException']


def connect(*args, **kwargs) -> MercutoClient:
    return MercutoClient().connect(*args, **kwargs)
