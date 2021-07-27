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

import globus_sdk


TRANSFER_FINISHED_STATUS = ("SUCCEEDED", "FAILED")


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


def parse_config(config_file):
    """Parse the config file"""
    if not config_file.exists():
        raise ValueError(f"Config file does not exist: {config_file}")
    config = configparser.ConfigParser()
    config.read(config_file)

    try:
        client_id = config["globus"]["clientid"]
    except KeyError:
        raise KeyError(f"Config file must have [globus] section with clientid")

    if not "sync" in config:
        raise KeyError("Config file must have [sync] section")
    sync_section = config["sync"]
    sync_info = {
        "src": sync_section["src_endpoint"],
        "dst": sync_section["dst_endpoint"],
        "path": sync_section["path"],
    }

    # deadline
    timelimitmins = config.getint("sync", "timelimitmins", fallback=1440)  # default is 24 hours
    now = datetime.datetime.utcnow()
    deadline = now + datetime.timedelta(minutes=timelimitmins)
    sync_info["deadline"] = str(deadline)

    print(f"Read config file {config_file}:")
    print(f"  src_endpoint: {sync_info['src']}")
    print(f"  dst_endpoint: {sync_info['dst']}")
    print(f"  path: {sync_info['path']}")
    print(f"  deadline: {deadline} (now: {now})")

    return client_id, sync_info


def get_transfer_client(client_id, client_secret):
    """Authenticate the app and Create the transfer client"""
    confidential_client = globus_sdk.ConfidentialAppAuthClient(
        client_id=client_id, client_secret=client_secret
    )
    scopes = "urn:globus:auth:scope:transfer.api.globus.org:all"
    cc_authorizer = globus_sdk.ClientCredentialsAuthorizer(confidential_client, scopes)
    transfer_client = globus_sdk.TransferClient(authorizer=cc_authorizer)

    return transfer_client


def transfer(tc, sync_info):
    """Start the transfer"""
    # initiate the data transfer to NeSI
    tdata = globus_sdk.TransferData(
        tc,
        sync_info["src"],
        sync_info["dst"],
        label="Syncing data test",
        sync_level="checksum",
        deadline=sync_info["deadline"],
    )

    # add the directory to the transfer
    tdata.add_item(sync_info["path"], sync_info["path"], recursive=True)

    # actually start the transfer
    transfer_result = tc.submit_transfer(tdata)
    task_id = transfer_result["task_id"]
    print("task_id =", transfer_result["task_id"])

    # print url for viewing changes
    url_string = 'https://app.globus.org/file-manager?' + \
        urllib.parse.urlencode({
            'origin_id': sync_info["src"],
            'origin_path': sync_info["path"],
            'destination_id': sync_info["dst"],
            'destination_path': sync_info["path"]
        })
    print('Visit the link below to see the changes:\n{}'.format(url_string))

    return task_id

def wait_for_transfer(tc, task_id):
    """Wait for the transfer to complete"""
    # the task id can be used to refer to this transfer
    # for example, here we wait for the data transfer to complete
    print(f"waiting for transfer {task_id} to complete...")
    while not tc.task_wait(task_id):
        print("waiting for transfer to complete...")
    print("transfer is complete")

def get_transfer_status(tc, task_id):
    """Prints info about a transfer, returns True if the transfer is still active"""
    # info about transfer
    task_info = tc.get_task(task_id)
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
    print(f"Transfer status for {task_id}:")
    for key in keys:
        print(f"  {key}: {task_info[key]}")

    return not task_info["status"] in TRANSFER_FINISHED_STATUS


def check_endpoints(tc, sync_info):
    res = tc.endpoint_autoactivate(sync_info["src"])
    if res["code"] == "AutoActivationFailed":
        raise RuntimeError("Could not activate src endpoint")

    res = tc.endpoint_autoactivate(sync_info["dst"])
    if res["code"] == "AutoActivationFailed":
        raise RuntimeError("Could not activate dst endpoint")


def read_cache(cache_file):
    """Read task ID from cache file"""
    if os.path.exists(cache_file):
        with open(cache_file) as fh:
            cache_dict = json.load(fh)
        try:
            task_id = cache_dict["task_id"]
        except KeyError:
            task_id = None
    else:
        task_id = None

    return task_id


def write_cache(cache_file, task_id):
    """Write the task_id to cache file"""
    print(f"Writing cache to {cache_file}")
    cache_dict = {
        "task_id": task_id,
    }
    with open(cache_file, "w") as fh:
        json.dump(cache_dict, fh, indent=4)


def main():
    # get command line args
    args = parse_args()

    # read config file
    client_id, sync_info = parse_config(args.config_file)

    # load the secret
    print(f"Loading client secret from {args.secret_file}")
    with open(args.secret_file) as fh:
        client_secret = fh.readline().strip()

    # make the globus transfer client
    tc = get_transfer_client(client_id, client_secret)

    # check endpoints are activated
    check_endpoints(tc, sync_info)

    # check for previous transfer
    stored_task_id = read_cache(args.cache_file)
    if stored_task_id is not None:
        print(f"Checking status of previous transfer: {stored_task_id}")
        transfer_active = get_transfer_status(tc, stored_task_id)
    else:
        transfer_active = False

    # start a new transfer if the previous one is not still running
    if transfer_active:
        print(f"Previous transfer ({stored_task_id}) is still active")
        task_id = stored_task_id
    elif not args.dry_run:
        print("Starting transfer")

        # start the transfer
        task_id = transfer(tc, sync_info)

        # write the cache file with transfer id
        write_cache(args.cache_file, task_id)

    # optionally wait for the transfer to complete
    if args.wait and not args.dry_run:
        print("Waiting for transfer to complete")

        # wait for tranfer to complete
        wait_for_transfer(tc, task_id)

        # print status
        get_transfer_status(tc, task_id)


if __name__ == "__main__":
    main()
