import requests

from ..exceptions import MercutoClientException, MercutoHTTPException

_PayloadValueType = str | float | int | None | bool
_PayloadListType = list[str] | list[float] | list[int] | list[_PayloadValueType]
_PayloadDictType = dict[str, '_PayloadValueType | _PayloadListType | _PayloadDictType']
PayloadType = dict[str, _PayloadValueType | _PayloadListType | _PayloadDictType]
_PayloadType = PayloadType  # For backwards compatibility


def raise_for_response(r: requests.Response) -> None:
    if 500 <= r.status_code < 600:
        raise MercutoClientException(f"Server error: {r.text}")
    if not (200 <= r.status_code < 300):
        try:
            detail = r.text
        except Exception:
            detail = str(r)
        raise MercutoHTTPException(detail, r.status_code)


_raise_for_response = raise_for_response  # For backwards compatibility
