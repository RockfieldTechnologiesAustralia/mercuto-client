from datetime import timedelta

from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict, TypeAdapter

_TimedeltaAdapter = TypeAdapter(timedelta)


def serialise_timedelta(td: timedelta) -> str:
    s = _TimedeltaAdapter.dump_python(td, mode='json')
    assert isinstance(s, str)
    return s


class BaseModel(_BaseModel):
    model_config = ConfigDict(
        extra='allow'
    )
