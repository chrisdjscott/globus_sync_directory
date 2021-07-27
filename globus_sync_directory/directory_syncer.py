
import logging
from pathlib import Path
import json

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
    def __init__(self, client_id: str, client_secret: str, cache_dir: Path, name: str, src_endpoint: str, dst_endpoint: str, dirpath: str):
        self._logger = logging.getLogger(f"DirectorySyncer::{name}")

        # make the transfer client
        self._transfer_client = self._make_transfer_client(client_id, client_secret)

        # check the endpoints can be connected
        self._check_endpoint(src_endpoint)
        self._src_endpoint = src_endpoint
        self._check_endpoint(dst_endpoint)
        self._dst_endpoint = dst_endpoint

        # check the directory exists on source endpoint
        self._dirpath = dirpath
        self._check_path_exists(src_endpoint, dirpath)

        # load the cache
        self._cache_file = cache_dir / f"{name}.json"
        self._load_cache()

        self._logger.debug(f'Created directory syncer: {src_endpoint}":"{dirpath}" -> "{dst_endpoint}"')

    def _make_transfer_client(self, client_id: str, client_secret: str) -> globus_sdk.TransferClient:
        confidential_client = globus_sdk.ConfidentialAppAuthClient(
            client_id=client_id, client_secret=client_secret
        )
        scopes = "urn:globus:auth:scope:transfer.api.globus.org:all"
        cc_authorizer = globus_sdk.ClientCredentialsAuthorizer(confidential_client, scopes)
        transfer_client = globus_sdk.TransferClient(authorizer=cc_authorizer)

        return transfer_client

    def _check_endpoint(self, endpoint_id: str):
        """Check the endpoint can be autoactivated otherwise raise an error"""
        res = self._transfer_client.endpoint_autoactivate(endpoint_id)
        if res["code"] == "AutoActivationFailed":
            raise RuntimeError(f"Could not activate endpoint: {endpoint_id}")

    def _check_path_exists(self, endpoint_id: str, dirpath: str):
        """Check the path exists on the endpoint otherwise raise an error"""
        pass

    def is_active(self):
        """Is there an active transfer"""
        return self._transfer_id is not None

    def run(self, start=True):
        """Run the transfer to synchronise the directories"""
        # if no active transfer, start one
        if self._transfer_id is None and start:
            # setting up the transfer data object
            tdata = globus_sdk.TransferData(
                self._transfer_client,
                self._src_endpoint,
                self._dst_endpoint,
                label="Syncing directories",
                sync_level="checksum",
            )

            # add the directory to the transfer
            tdata.add_item(self._dirpath, self._dirpath, recursive=True)

            # actually start the transfer
            transfer_result = self._transfer_client.submit_transfer(tdata)
            self._transfer_id = transfer_result["task_id"]
            self._logger.debug(f"Started transfer with id: {self._transfer_id}")

        # print some info about the current transfer, if there is one
        if self._transfer_id is not None:
            task_info = self._transfer_client.get_task(self._transfer_id)
            self._logger.debug(f"Transfer {self._transfer_id}:")
            keys = [
                "status",
                "deadline",
                "completion_time",
                "directories",
                "files",
                "files_skipped",
                "files_transferred",
                "bytes_transferred",
                "bytes_checksummed",
            ]
            for key in keys:
                self._logger.debug(f"{key}: {task_info[key]}")
            if task_info["status"] != "ACTIVE":
                self._logger.debug("Transfer is no longer active")
                self._transfer_id = None

        # write the cache
        self._write_cache()

    def _write_cache(self):
        """write the cache file"""
        cache_dict = {
            "transfer_id": self._transfer_id,
        }
        with self._cache_file.open("w") as fh:
            json.dump(cache_dict, fh, indent=4)
        self._logger.debug(f"Written cache file: {self._cache_file}")

    def _load_cache(self):
        """Load the cache file"""
        if self._cache_file.exists():
            with self._cache_file.open() as fh:
                cache_dict = json.load(fh)
            self._logger.debug(f"Loaded cache file: {self._cache_file}")
            self._logger.debug(f"Cache contents: {cache_dict}")
            self._transfer_id = cache_dict["transfer_id"]
        else:
            self._transfer_id = None
