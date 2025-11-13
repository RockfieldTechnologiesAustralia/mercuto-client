# import getpass
# import os
# import time
#
# import paramiko
# from paramiko import RSAKey, SSHClient
# from paramiko.config import SSH_PORT

# class SCPBackup(Backup):
#
#     def __init__(self, url: ParseResult):
#         self.params: Optional[SCPBackupParams] = None
#         super().__init__(url)
#         self.ssh_client = SSHClient()
#         self.agent = paramiko.Agent()
#         self._init_connection()
#
#     def _init_connection(self):
#         user_config = paramiko.SSHConfig()
#         user_config_file = os.path.expanduser("~/.ssh/config")
#         if os.path.exists(user_config_file):
#             with open(user_config_file) as f:
#                 user_config.parse(f)
#
#         if self.url.hostname is None:
#             raise RuntimeError("Hostname should not be None")
#
#         host_config = user_config.lookup(self.url.hostname)
#
#         self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#
#         host = None
#         if 'hostname' in host_config:
#             host = host_config['hostname']
#
#         if host is None and self.url.hostname is not None:
#             host = self.url.hostname
#
#         user = None
#         if 'user' in host_config:
#             user = host_config['user']
#
#         port = None
#         if 'port' in host_config:
#             port = int(host_config['port'])
#
#         if port is None and self.url.port is not None:
#             port = self.url.port
#
#         if port is None:
#             port = SSH_PORT
#
#         if self.url.username is not None:
#             user = self.url.username
#
#         if user is None:
#             user = getpass.getuser()
#             logger.info(f"Using default user {user}")
#
#         kwargs: Dict[str, Any] = {}
#
#         keys = self.agent.get_keys()
#         found = False
#         our_key = None
#         if self.params is not None and self.params.private_key is not None:
#             our_key = RSAKey.from_private_key_file(self.params.private_key)
#             for key in keys:
#                 if our_key.algorithm_name == key.algorithm_name:
#                     if our_key.fingerprint == key.fingerprint:
#                         found = True
#
#         if not found and our_key is not None:
#             kwargs['pkey'] = our_key
#
#         if self.url.password is not None:
#             kwargs['password'] = self.url.password
#
#         self.ssh_client.connect(hostname=host, port=port, username=user, **kwargs)
#
#     def validate_url(self):
#         query = self.decode_query()
#         self.params = SCPBackupParams.load_qs(query)
#
#     def process_file(self, filename: str) -> bool:
#         pth = Path(filename)
#         sftp_client = self.ssh_client.open_sftp()
#         sftp_client.chdir(self.url.path)
#         with open(filename, "rb") as d_in:
#             data = d_in.read(4096)
#             with sftp_client.open(pth.name, mode='wb') as d_out:
#                 while len(data) > 0:
#                     d_out.write(data)
#                     data = d_in.read(4096)
#         if self.params is not None and self.params.script is not None:
#             dest_folder = PosixPath(self.url.path)
#             fn = Path(filename)
#             _stdin, _stdout, _stderr = self.ssh_client.exec_command(self.params.script.format(destination=dest_folder/fn.name))
#             exit_status = _stdout.channel.recv_exit_status()
#             logger.debug(f"Script exit status: {exit_status}")
#             logger.debug(f"Script stdout: {_stdout.read().decode('utf-8', errors='ignore')}")
#             logger.debug(f"Script stderr: {_stderr.read().decode('utf-8', errors='ignore')}")
#             return exit_status == 0
#         return True
