"""
Sync directories between Globus shared collections.

"""
import os
import argparse
import configparser
from pathlib import Path
import logging
import urllib
import json
import datetime
import subprocess

import globus_sdk


TRANSFER_FINISHED_STATUS = ("SUCCEEDED", "FAILED")


class Transfer:
    """
    A single directory sync

    """
    def __init__(self, name, src_endpoint, src_path, dst_endpoint, dst_path, deadline):
        self._name = name
        self._src_endpoint = src_endpoint
        self._src_path = src_path
        self._dst_endpoint = dst_endpoint
        self._dst_path = dst_path
        self._deadline = deadline
        self._transfer_id = None
        self._msg = []

    def __repr__(self):
        return f"{self._name}: ({self._src_endpoint}:{self._src_path} -> {self._dst_endpoint}:{self._dst_path})"

    def set_transfer_client(self, transfer_client):
        """Reference to the transfer client"""
        self._tc = transfer_client

    def check_endpoints(self):
        """Check the endpoints can be activated"""
        res = self._tc.endpoint_autoactivate(self._src_endpoint)
        if res["code"] == "AutoActivationFailed":
            raise RuntimeError(f"Could not activate src endpoint for {self._name}")

        res = self._tc.endpoint_autoactivate(self._dst_endpoint)
        if res["code"] == "AutoActivationFailed":
            raise RuntimeError(f"Could not activate dst endpoint for {self._name}")

    def read_cache(self, cache):
        """Reference to the cache dict"""
        # check if set
        if self._name in cache:
            self._transfer_id = cache[self._name]

    def set_cache(self, cache):
        """Set cache value"""
        if self._transfer_id is not None:
            cache[self._name] = self._transfer_id
        else:
            if self._name in cache:
                cache.pop(self._name)

    def _get_transfer_status(self):
        """Checks for an active transfer, reports info"""
        if self._transfer_id is not None:
            # info about transfer
            task_info = self._tc.get_task(self._transfer_id)
            keys = [
                "status",
                "request_time",
                "deadline",
                "completion_time",
                "directories",
                "files",
                "files_skipped",
                "files_transferred",
                "bytes_transferred",
                "bytes_checksummed",
            ]

            # message
            msg = [f'[{self._name}]: Status of transfer with id {self._transfer_id}:']
            for key in keys:
                msg.append(f"[{self._name}]:   {key}: {task_info[key]}")
            self._msg.extend(msg)
            self._msg.append("")

            # print to standard output
            print("\n".join(msg))

            # if the transfer is finished, then remove the id
            if task_info["status"] in TRANSFER_FINISHED_STATUS:
                self._transfer_id = None

    def get_msg(self):
        """Return the message"""
        return self._msg

    def process(self, start=True):
        """Process the transfer or print status if already active"""
        print(f"Processing: {self._name}")

        # if there was an id stored in the cache, check if it is active
        self._msg = [f"[{self._name}]: Checking status of current transfer (if any)..."]
        self._get_transfer_status()

        if self._transfer_id is None and start:
            # start a new transfer
            self._msg.append(f"[{self._name}]: Starting new transfer...")
            self._transfer()

            # check status of newly started transfer
            self._msg.append(f"[{self._name}]: Checking status of started transfer...")
            self._get_transfer_status()

    def _transfer(self):
        """Start the transfer"""
        # initiate the data transfer to NeSI
        tdata = globus_sdk.TransferData(
            self._tc,
            self._src_endpoint,
            self._dst_endpoint,
            label=f"Syncing data for {self._name}",
            sync_level="checksum",
            deadline=self._deadline,
        )

        # add the directory to the transfer
        tdata.add_item(self._src_path, self._dst_path, recursive=True)

        # actually start the transfer
        transfer_result = self._tc.submit_transfer(tdata)
        self._transfer_id = transfer_result["task_id"]
        print(f"transfer id: {self._transfer_id}")
        self._msg.append(f"[{self._name}]: Transfer started with id: {self._transfer_id}")

        # print url for viewing changes
        url_string = 'https://app.globus.org/file-manager?' + \
            urllib.parse.urlencode({
                'origin_id': self._src_endpoint,
                'origin_path': self._src_path,
                'destination_id': self._dst_endpoint,
                'destination_path': self._dst_path,
            })
        print('Visit the link below to see the changes:\n{}'.format(url_string))
        self._msg.append(f"[{self._name}]: Visit the link below to see the changes:\n{url_string}")
        self._msg.append("")


class Syncer:
    """
    Sync directories between Globus endpoints

    """
    def __init__(self, config_file, secret_file, cache_file):
        self._config_file = config_file
        self._cache_file = cache_file

        # parse the config file
        self._parse_config()

        # load the secret
        print(f"Loading client secret from {secret_file}")
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
        print(f"Reading config file {config_file}:")
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
        print(f"  deadline: {self._deadline} (now: {now})")

        # email notification
        self._notify_email = config.get("notification", "email", fallback=None)
        print(f"  notify email: {self._notify_email}")

        # read the transfer sections
        other_sections = ("schedule", "globus", "notification")
        transfer_sections = [s for s in config.sections() if s not in other_sections]
        self._transfers = []
        for transfer_section in transfer_sections:
            src_endpoint = config[transfer_section]["src_endpoint"]
            src_path = config.get(transfer_section, "src_path", fallback="/")
            dst_endpoint = config[transfer_section]["dst_endpoint"]
            dst_path = config.get(transfer_section, "dst_path", fallback=src_path)
            self._transfers.append(Transfer(transfer_section, src_endpoint, src_path, dst_endpoint, dst_path, self._deadline))
            print(f'  adding transfer: {self._transfers[-1]}')

    def _create_transfer_client(self):
        """Authenticate the app and Create the transfer client"""
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
        print(f"Checking access to the endpoints")
        for t in self._transfers:
            t.check_endpoints()

    def _read_cache(self):
        """Read cache file"""
        print(f"Reading cache file: {self._cache_file}")
        if os.path.exists(self._cache_file):
            with open(self._cache_file) as fh:
                self._cache = json.load(fh)
        else:
            self._cache = {}
        print(self._cache)

        for t in self._transfers:
            t.read_cache(self._cache)

    def _write_cache(self):
        """Write the task_id to cache file"""
        print(f"Writing cache to {self._cache_file}")
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
                print(f"notifying by email: {self._notify_email}")
                cmdargs = ["/usr/bin/mail", "-s", '"Globus Sync Directory status"', "--"]
                cmdargs.extend(self._notify_email.split(","))
                cmd = " ".join(cmdargs)
                status = subprocess.run(cmd, shell=True, universal_newlines=True, input="\n".join(output))
                if status.returncode:
                    print("Warning: sending email failed")
                    print(cmd)


def parse_args():
    """Parse command line arguments"""
    default_secret_file = Path.home() / f".globus_sync_directory_secret"

    parser = argparse.ArgumentParser(description="Sync directories with Globus")

    parser.add_argument("-c", "--config-file", default="config.ini", type=Path, help="Path to config file (default=config.ini)")
    parser.add_argument("-s", "--secret-file", default=default_secret_file, type=Path, help=f"Path to secret file (default={default_secret_file})")
    parser.add_argument("-t", "--cache-file", default="globus_sync_directory.json", type=Path, help="Path to cache file (default=globus_sync_directory.json)")
    parser.add_argument("-w", "--wait", action="store_true", help="Wait for the transfer to complete")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Do everything except submitting or waiting for a transfer")

    args = parser.parse_args()

    return args


def main():
    print("\nRunning globus_sync_directory...")
    # get command line args
    args = parse_args()

    # create the directory syncer
    s = Syncer(args.config_file, args.secret_file, args.cache_file)

    # process the transfers
    s.process(start=(not args.dry_run))


if __name__ == "__main__":
    main()
