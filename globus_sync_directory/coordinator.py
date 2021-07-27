
import configparser
import typing as T
from pathlib import Path
import logging
import time

from .directory_syncer import DirectorySyncer


class Coordinator(object):
    """
    Load config, set up sync'ers and run them

    """
    def __init__(self, config_file: Path, secret_file: Path, cache_dir: Path):
        self._logger = logging.getLogger("Coordinator")
        client_secret = self._load_secret(secret_file)
        cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._syncers = self._load_config(config_file, client_secret, cache_dir)

    def _load_config(self, config_file: Path, client_secret: str, cache_dir: Path) -> T.Iterable[DirectorySyncer]:
        """
        Load the config file

        """
        self._logger.info(f"Loading config file: {config_file}")

        if not config_file.exists():
            raise ValueError(f"Config file does not exist: {config_file}")
        config = configparser.ConfigParser()
        config.read(config_file)

        non_sync_sections = ["app", "globus"]

        try:
            client_id = config["globus"]["clientid"]
        except KeyError:
            raise KeyError(f"Config file must have [globus] section with clientid parameter")

        sync_section_names = [s for s in config.sections() if s not in non_sync_sections]
        if len(sync_section_names) == 0:
            raise KeyError("Config file has no sync sections")
        self._logger.debug(f"Found sync sections in config: {sync_section_names}")

        # loop over directories to sync
        syncers = []
        for name in sync_section_names:
            try:
                src_endpoint = config[name]["src_endpoint"]
                dst_endpoint = config[name]["dst_endpoint"]
                dirpath = config[name]["path"]
            except KeyError:
                raise KeyError(f'Sync section "{name}" must specfify "src_endpoint", "dst_endpoint" and "path"')

            ds = DirectorySyncer(client_id, client_secret, cache_dir, name, src_endpoint, dst_endpoint, dirpath)
            syncers.append(ds)

        return syncers

    def _load_secret(self, secret_file: Path) -> str:
        with open(secret_file) as fh:
            client_secret = fh.readline().strip()

        return client_secret

    def run(self):
        """Run the coordinator"""
        # for debugging, start a transfer...
        self._logger.debug("Starting transfers")
        for ds in self._syncers:
            ds.run(start=True)

        # ...and check every 10s for them to complete
        self._logger.debug("Waiting for transfers to complete")
        active = True
        while active:
            time.sleep(10)
            self._logger.debug("Checking...")
            active = False
            for ds in self._syncers:
                ds.run(start=False)
                if ds.is_active():
                    active = True
