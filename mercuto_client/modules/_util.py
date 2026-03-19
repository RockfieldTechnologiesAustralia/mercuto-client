from datetime import timedelta
from typing import Final

from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict, TypeAdapter

# Sentinel used by partial-update (PATCH) client methods to distinguish
# "caller did not provide this argument" from "caller explicitly passed None".
_UNSET: Final = object()

_TimedeltaAdapter = TypeAdapter(timedelta)


def serialise_timedelta(td: timedelta) -> str:
    s = _TimedeltaAdapter.dump_python(td, mode='json')
    assert isinstance(s, str)
    return s


class BaseModel(_BaseModel):
    model_config = ConfigDict(
        extra='allow'
    )
