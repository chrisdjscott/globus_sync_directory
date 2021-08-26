
import urllib

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