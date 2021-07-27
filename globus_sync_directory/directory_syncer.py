
import logging

import globus_sdk


class DirectorySyncer(object):
    """
    Keeps a directory synchronised

    - if there is an active transfer (check cache), act on that
       1. check the status, running or completed
       2. report status
       3. update cache
    - if there is not an active transfer, check whether we should start a new one
      - if starting a new one
        1. start the transfer
        2. report status
        3. update cache


    """
    def __init__(self, client_id: str, client_secret: str, name: str, src_endpoint: str, dst_endpoint: str, dirpath: str):
        self._logger = logging.getLogger("DirectorySyncer")
        self._transfer_client = self._make_transfer_client(client_id, client_secret)
        self._src_endpoint = src_endpoint
        self._dst_endpoint = dst_endpoint
        self._dirpath = dirpath
        self._logger.debug(f'Created directory syncer "{name}": "{src_endpoint}":"{dirpath}" -> "{dst_endpoint}"')

    def _make_transfer_client(self, client_id: str, client_secret: str) -> globus_sdk.TransferClient:
        pass


