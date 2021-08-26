
import os
import configparser
import json
import datetime
import subprocess
import logging

import globus_sdk

from .transfer import Transfer


class Syncer:
    """
    Sync directories between Globus endpoints

    """
    def __init__(self, config_file, secret_file, cache_file):
        self._logger = logging.getLogger("Syncer")
        self._config_file = config_file
        self._cache_file = cache_file

        # parse the config file
        self._parse_config()

        # load the secret
        self._logger.info(f"Loading client secret from {secret_file}")
        with open(secret_file) as fh:
            self._client_secret = fh.readline().strip()

        # create the Globus transfer client
        self._create_transfer_client()

        # check access to the endpoints
        self._check_endpoints()

        # read in the cache
        self._read_cache()

    def _parse_config(self):
        """Parse the config file"""
        config_file = self._config_file
        if not config_file.exists():
            raise ValueError(f"Config file does not exist: {config_file}")
        self._logger.info(f"Reading config file {config_file}:")
        config = configparser.ConfigParser()
        config.read(config_file)

        # read the Globus application client ID
        try:
            self._client_id = config["globus"]["clientid"]
        except KeyError:
            raise KeyError(f"Config file must have [globus] section with clientid")

        # transfer deadline
        timelimitmins = config.getint("schedule", "timelimitmins", fallback=1440)  # default is 24 hours
        now = datetime.datetime.utcnow()
        deadline = now + datetime.timedelta(minutes=timelimitmins)
        self._deadline = str(deadline)
        self._logger.info(f"  deadline: {self._deadline} (now: {now})")

        # email notification
        self._notify_email = config.get("notification", "email", fallback=None)
        self._logger.info(f"  notify email: {self._notify_email}")

        # read the transfer sections
        other_sections = ("schedule", "globus", "notification")
        transfer_sections = [s for s in config.sections() if s not in other_sections]
        self._transfers = []
        for transfer_section in transfer_sections:
            self._logger.debug(f"Reading transfer section: {transfer_section}")
            try:
                src_endpoint = config[transfer_section]["src_endpoint"]
            except KeyError:
                self._logger.error(f"No 'src_endpoint' in transfer section '{transfer_section}'")
                raise
            src_path = config.get(transfer_section, "src_path", fallback="/")
            try:
                dst_endpoint = config[transfer_section]["dst_endpoint"]
            except KeyError:
                self._logger.error(f"No 'dst_endpoint' in transfer section '{transfer_section}'")
                raise
            dst_path = config.get(transfer_section, "dst_path", fallback=src_path)
            self._transfers.append(Transfer(transfer_section, src_endpoint, src_path, dst_endpoint, dst_path, self._deadline))
            self._logger.info(f'  adding transfer: {self._transfers[-1]}')

    def _create_transfer_client(self):
        """Authenticate the app and Create the transfer client"""
        self._logger.debug("Creating transfer client")

        # create the transfer client
        confidential_client = globus_sdk.ConfidentialAppAuthClient(
            client_id=self._client_id, client_secret=self._client_secret
        )
        scopes = "urn:globus:auth:scope:transfer.api.globus.org:all"
        cc_authorizer = globus_sdk.ClientCredentialsAuthorizer(confidential_client, scopes)
        self._transfer_client = globus_sdk.TransferClient(authorizer=cc_authorizer)

        # pass transfer client
        for t in self._transfers:
            t.set_transfer_client(self._transfer_client)

    def _check_endpoints(self):
        """Check that the app has access to the endpoints"""
        self._logger.debug(f"Checking access to the endpoints")
        for t in self._transfers:
            t.check_endpoints()

    def _read_cache(self):
        """Read cache file"""
        self._logger.debug(f"Reading cache file: {self._cache_file}")
        if os.path.exists(self._cache_file):
            with open(self._cache_file) as fh:
                self._cache = json.load(fh)
        else:
            self._cache = {}
        self._logger.debug(self._cache)

        for t in self._transfers:
            t.read_cache(self._cache)

    def _write_cache(self):
        """Write the task_id to cache file"""
        self._logger.debug(f"Writing cache to {self._cache_file}")
        with open(self._cache_file, "w") as fh:
            json.dump(self._cache, fh, indent=4)

    def process(self, start=True):
        """process each transfer"""
        # process the transfers
        output = []
        for t in self._transfers:
            t.process(start=start)
            t.set_cache(self._cache)
            output.extend(t.get_msg())

        # write the cache file
        self._write_cache()

        # notify
        if len(output):
            # optionally, email
            if self._notify_email is not None:
                self._logger.info(f"notifying by email: {self._notify_email}")
                cmdargs = ["/usr/bin/mail", "-s", '"Globus Sync Directory status"', "--"]
                cmdargs.extend(self._notify_email.split(","))
                cmd = " ".join(cmdargs)
                status = subprocess.run(cmd, shell=True, universal_newlines=True, input="\n".join(output))
                if status.returncode:
                    self._logger.warning("Warning: sending email failed")
                    self._logger.warning(cmd)
