# Mercuto File Ingester
Utility for on-site buffering of files and upload into Mercuto
This process starts an FTP server and uploads files into a directory.
Any file in the directory is uploaded into Mercuto for the given project.
## Usage:
```shell
python.exe -m mercuto_client.ingester -p PROJECT_CODE -k API_KEY --verbose
```

Alternative one-liner using UV:

```shell
uv run --with mercuto-client -m mercuto_client.ingester --api-key 12345 --project 12345
```