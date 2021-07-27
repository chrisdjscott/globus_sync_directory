
import configparser
import typing as T
from pathlib import Path
import logging

from .directory_syncer import DirectorySyncer


class Coordinator(object):
    """
    Load config, set up sync'ers and run them

    """
    def __init__(self, config_file: Path, secret_file: Path, cache_dir: Path):
        self._logger = logging.getLogger("Coordinator")
        self._cache_dir = cache_dir
        client_secret = self._load_secret(secret_file)
        self._setup_cache_dir(cache_dir)
        self._syncers = self._load_config(config_file, client_secret)

    def _load_config(self, config_file: Path, client_secret: str) -> T.Iterable[DirectorySyncer]:
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

            ds = DirectorySyncer(client_id, client_secret, name, src_endpoint, dst_endpoint, dirpath)
            syncers.append(ds)

        return syncers

    def _load_secret(self, secret_file: Path) -> str:
        with open(secret_file) as fh:
            client_secret = fh.readline().strip()

        return client_secret

    def _setup_cache_dir(self, cache_dir: Path):
        pass
