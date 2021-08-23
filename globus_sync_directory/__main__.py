"""
Sync directories between Globus shared collections.

"""
import argparse
from pathlib import Path

from .syncer import Syncer


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
