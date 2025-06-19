# Mercuto File Ingester
Utility for on-site buffering of files and upload into Mercuto
This process starts an FTP server and uploads files into a directory.
Any file in the directory is uploaded into Mercuto for the given project.
## Installation
Install this module separately using:
`uv add git+https://github.com/RockfieldTechnologiesAustralia/mercuto-client@0.2.0[ingester]`
or 
`pip install git+https://github.com/RockfieldTechnologiesAustralia/mercuto-client@0.2.0[ingester]`

## Usage:
```shell
python.exe -m mercuto_client.ingester -p PROJECT_CODE -k API_KEY --verbose
```