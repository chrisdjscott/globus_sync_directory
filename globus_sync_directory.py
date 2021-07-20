"""
Sync directories between Globus shared collections.

"""
import argparse
import configparser
from pathlib import Path
import logging

import globus_sdk


SCRIPT_NAME = "globus_sync_directory"


def parse_args():
    default_secret_file = Path.home() / f".{SCRIPT_NAME}.secret"

    parser = argparse.ArgumentParser(description="Sync directories with Globus")

    parser.add_argument("-c", "--config-file", default="config.ini", type=Path, help="Path to config file")
    parser.add_argument("-s", "--secret-file", default=default_secret_file, type=Path, help="Path to secret file")
    parser.add_argument("-t", "--cache-file", default="cache.json", type=Path, help="Path to cache file")

    args = parser.parse_args()

    return args


def parse_config(config_file):
    if not config_file.exists():
        raise ValueError(f"Config file does not exist: {config_file}")
    config = configparser.ConfigParser()
    config.read(config_file)

    try:
        client_id = config["app"]["clientid"]
    except KeyError:
        raise KeyError(f"Config file must have [app] section with clientid")

    if not "sync" in config:
        raise KeyError("Config file must have [sync] section")
    sync_section = config["sync"]
    sync_info = {
        "src": sync_section["src_endpoint"],
        "dst": sync_section["dst_endpoint"],
        "path": sync_section["path"],
    }

    return client_id, sync_info


def get_transfer_client(client_id, client_secret):
    confidential_client = globus_sdk.ConfidentialAppAuthClient(
        client_id=client_id, client_secret=client_secret
    )
    scopes = "urn:globus:auth:scope:transfer.api.globus.org:all"
    cc_authorizer = globus_sdk.ClientCredentialsAuthorizer(confidential_client, scopes)
    transfer_client = globus_sdk.TransferClient(authorizer=cc_authorizer)

    return transfer_client


def transfer(tc, sync_info):
    # initiate the data transfer to NeSI
    tdata = globus_sdk.TransferData(tc,
                                    sync_info["src"],
                                    sync_info["dst"],
                                    label="Syncing data test",
                                    sync_level="checksum")

    # add the directory to the transfer
    tdata.add_item(sync_info["path"], sync_info["path"], recursive=True)

    # actually start the transfer
    transfer_result = tc.submit_transfer(tdata)
    task_id = transfer_result["task_id"]
    print("task_id =", transfer_result["task_id"])

    # the task id can be used to refer to this transfer
    # for example, here we wait for the data transfer to complete
    print("waiting for transfer to complete...")
    while not tc.task_wait(task_id, timeout=10, polling_interval=10):
        print("waiting for transfer to complete...")
    print("transfer is complete")

    # info about transfer
    task_info = tc.get_task(task_id)
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
        print(key, ":", task_info[key])


def check_endpoints(tc, sync_info):
    res = tc.endpoint_autoactivate(sync_info["src"])
    if res["code"] == "AutoActivationFailed":
        raise RuntimeError("Could not activate src endpoint")

    res = tc.endpoint_autoactivate(sync_info["dst"])
    if res["code"] == "AutoActivationFailed":
        raise RuntimeError("Could not activate dst endpoint")


def main():
    # get command line args
    args = parse_args()
    print(args)

    # read config file
    client_id, sync_info = parse_config(args.config_file)
    print(sync_info)

    # load the secret
    with open(args.secret_file) as fh:
        client_secret = fh.readline().strip()

    # make the globus transfer client
    tc = get_transfer_client(client_id, client_secret)
    print(tc)

    # check endpoints are activated
    check_endpoints(tc, sync_info)

    # run the transfer
    transfer(tc, sync_info)


if __name__ == "__main__":
    main()
