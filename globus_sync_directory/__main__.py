
import typing as T
import argparse
from pathlib import Path
import logging

from . import coordinator


def parse_args() -> argparse.Namespace:
    default_secret_file = Path.home() / f".globus_sync_directory_secret"
    default_cache_dir = Path.home() / f".cache/globus_sync_directory"

    parser = argparse.ArgumentParser(description="Sync directories with Globus")

    parser.add_argument("-c", "--config-file", default="config.ini", type=Path, help="Path to config file")
    parser.add_argument("-s", "--secret-file", default=default_secret_file, type=Path, help="Path to secret file")
    parser.add_argument("-d", "--cache-dir", default=default_cache_dir, type=Path, help="Path to cache directory")

    args = parser.parse_args()

    return args


def main():
    args = parse_args()

    # set up logging
    logging.basicConfig(
        format="[%(asctime)s] %(name)s %(funcName)s():%(lineno)d %(levelname)s: %(message)s",
        level=logging.DEBUG,  # TODO: parameter
    )
    # different level on imported modules...
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("globus_sdk").setLevel(logging.WARNING)

    # create the coordinator
    c = coordinator.Coordinator(args.config_file, args.secret_file, args.cache_dir)
    c.run()



if __name__ == "__main__":
    main()
