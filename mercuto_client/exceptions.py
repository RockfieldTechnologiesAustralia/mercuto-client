import json
from typing import Any


class MercutoClientException(Exception):
    pass


class MercutoHTTPException(MercutoClientException):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    def json(self) -> Any:
        return json.loads(self.message)

    def __str__(self) -> str:
        return f"MercutoHTTPException(status_code='{self.status_code}', message='{self.message}')"
