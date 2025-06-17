import json


class MercutoClientException(Exception):
    pass


class MercutoHTTPException(MercutoClientException):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    def json(self) -> dict:
        return json.loads(self.message)
