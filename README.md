# Mercuto Client Python Library

Library for interfacing with Rockfield's Mercuto public API.
This library is in an early development state and is subject to major structural changes at any time.

(Visit our Github Repository)[https://github.com/RockfieldTechnologiesAustralia/mercuto-client]

## Installation
Install from PyPi: `pip install mercuto-client` or adding the same line into your `requirements.txt`.

## Basic Usage

Use the `connect()` function exposed within the main package and provide your API key.

```python
from mercuto_client import connect

client = connect(api_key="<YOUR API KEY>")
print(client.core().list_projects())

# Logout after finished.
client.logout()

```

You can also use the client as a context manager. It will logout automatically.

```python
from mercuto_client import MercutoClient

with MercutoClient.as_credentials(api_key='<YOUR API KEY>') as client:
    print(client.core().list_projects())
```

## Device functions

Device types can declare functions with additional suggested metadata fields and channels.
Use `device_type.functions` or `device_type.get_function(key)` to look them up;
`get_function` returns `None` for an unknown key. Types without functions have an empty list.
A device records its selected function in `device.function` (`None` when unset).

```python
assets = client.assets()
device_type = assets.get_device_type(device_type_code)
function = device_type.get_function("natural_frequency")
if function is not None:
    device = assets.create_device(
        project=project_code,
        label="Deck vibration meter",
        device_type=device_type.code,
        function=function.key,
    )
    # Omitting function preserves the current selection.
    assets.update_device(code=device.code, label="Renamed vibration meter")
    # Explicit None clears it; a string selects a different function.
    assets.update_device(code=device.code, label=device.label, function=None)
```

The server validates the selected function against the device type. The mock client
stores the value without validating it, with the same keep/set/clear update behaviour.

## Current Status
This library is incomplete and may not be fully compliant with the latest Mercuto version. It is only updated periodically and provided for use without any warranty or guarantees.

- [x] API Based login (Completed)
- [ ] Username/password login

## Running tests
Install test packages:
`python -m uv sync --group tests`
Run tests:
`uv run pytest`