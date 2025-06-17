# Mercuto Client Python Library

Library for interfacing with Rockfield's Mercuto public API.
This library is in an early development state and is subject to major structural changes at any time.

## Installation
Currently this library is not available on any package repository. It can be installed directly from Github using:
`pip install git+https://github.com/RockfieldTechnologiesAustralia/mercuto-client@0.1.0` or adding the same line into 
your `requirements.txt`.

## Basic Usage

Use the `connect()` function exposed within the main package and provide your API key.

```python
from mercuto_client import connect

client = connect(api_key="<YOUR API KEY>")
print(client.projects().get_projects())

# Logout after finished.
client.logout()

```

You can also use the client as a context manager. It will logout automatically.

```python
from mercuto_client import MercutoClient

with MercutoClient.as_credentials(api_key='<YOUR API KEY>') as client:
    print(client.projects().get_projects())
```

## Current Status
This library is incomplete and may not be fully compliant with the latest Mercuto version. It is only updated periodically and provided for use without any warranty or guarantees.

- [x] API Based login (Completed)
- [ ] Username/password login