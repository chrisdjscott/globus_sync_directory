"""
Sync directories between Globus shared collections.

"""
import argparse
from pathlib import Path
import logging

from .syncer import Syncer


def parse_args():
    """Parse command line arguments"""
    default_secret_file = Path.home() / f".globus_sync_directory_secret"

    parser = argparse.ArgumentParser(description="Sync directories with Globus")

    parser.add_argument("-c", "--config-file", default="config.ini", type=Path, help="Path to config file (default=config.ini)")
    parser.add_argument("-s", "--secret-file", default=default_secret_file, type=Path, help=f"Path to secret file (default={default_secret_file})")
    parser.add_argument("-t", "--cache-file", default="globus_sync_directory.json", type=Path, help="Path to cache file (default=globus_sync_directory.json)")
    parser.add_argument("-d", "--dont-start", action="store_true", help="Do not start a transfer")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only display warnings or errors")

    args = parser.parse_args()

    return args


def main():
    # get command line args
    args = parse_args()

    # logging
    if args.verbose:
        logging_level = logging.DEBUG
    elif args.quiet:
        logging_level = logging.WARNING
    else:
        logging_level = logging.INFO
    logging.basicConfig(
        level=logging_level,
        format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
    )
    logging.getLogger("globus_sdk").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    print()
    logging.info("Running globus_sync_directory...")

    # create the directory syncer
    s = Syncer(args.config_file, args.secret_file, args.cache_file)

    # process the transfers
    s.process(start=(not args.dont_start))


if __name__ == "__main__":
    main()
