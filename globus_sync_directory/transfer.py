
import os
import urllib
import logging

import globus_sdk

from . import email


TRANSFER_FINISHED_STATUS = ("SUCCEEDED", "FAILED")
STATUS_KEYS = [
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


class Transfer:
    """
    A single directory sync

    """
    def __init__(self, name, src_endpoint, src_path, dst_endpoint, dst_path, deadline, email, delete, sync_level):
        self._logger = logging.getLogger(name)
        self._name = name
        self._src_endpoint = src_endpoint
        self._src_path = src_path
        self._dst_endpoint = dst_endpoint
        self._dst_path = dst_path
        self._deadline = deadline
        self._transfer_id = None
        self._transfer_client = None
        self._client_id = None
        self._email = email
        self._delete = delete
        self._deletion_id = None
        self._msg = []
        self._sync_level = sync_level
        self._sent_success_email = False

    def __repr__(self):
        return f"{self._name}: ({self._src_endpoint}:{self._src_path} -> {self._dst_endpoint}:{self._dst_path}), delete={self._delete}, sync_level={self._sync_level}"

    def set_transfer_client(self, transfer_client, client_id):
        """Reference to the transfer client"""
        self._tc = transfer_client
        self._client_id = client_id

    def _check_endpoint(self, name, endpoint, path=None):
        """Check a single endpoint"""
        errors = False

        try:
            # try to autoactivate
            res = self._tc.endpoint_autoactivate(endpoint)

        except globus_sdk.TransferAPIError as exc:
            # pick up transfer api errors
            self._logger.error(f"Error while checking {name} endpoint ({exc.code}):")
            self._logger.error(f"  {exc.message}")
            if exc.message == "Not authorized for that endpoint":
                self._logger.error(f'  Make sure you have shared the endpoint with the app: "{self._client_id}@clients.auth.globus.org"')
            errors = True

        else:
            # check if response says auto activation failed
            if res["code"] == "AutoActivationFailed":
                self._logger.error(f"Could not autoactivate {name} endpoint ({endpoint})")
                errors = True

            elif path is not None:
                # check the path exists if given
                try:
                    res = self._tc.operation_ls(endpoint, path=path)
                except globus_sdk.TransferAPIError as exc:
                    self._logger.error(f"Error listing {name} directory ({exc.code})")
                    self._logger.error(f"  {exc.message}")
                    errors = True

        return errors

    def check_endpoints(self):
        """Check the endpoints can be activated"""
        # check we can access the source endpoint and path
        errors_src = self._check_endpoint("source", self._src_endpoint, path=self._src_path)

        # check we can access the destination endpoint
        errors_dst = self._check_endpoint("destination", self._dst_endpoint)

        # return True if there were errors
        if errors_src or errors_dst:
            return True
        else:
            return False

    def read_cache(self, cache):
        """Reference to the cache dict"""
        # check if set
        if self._name in cache:
            d = cache[self._name]
            self._logger.debug(f"Loading cache: {d}")
            if "transfer_id" in d:
                self._transfer_id = d["transfer_id"]
            if "deletion_id" in d:
                self._deletion_id = d["deletion_id"]
            if "sent_success_email" in d:
                self._sent_success_email = d["sent_success_email"]

    def set_cache(self, cache):
        """Set cache value"""
        d = {}
        if self._transfer_id is not None:
            d["transfer_id"] = self._transfer_id
        if self._deletion_id is not None:
            d["deletion_id"] = self._deletion_id
        if self._sent_success_email:
            d["sent_success_email"] = self._sent_success_email

        if len(d):
            cache[self._name] = d
            self._logger.debug(f"Setting cache: {d}")
        else:
            if self._name in cache:
                cache.pop(self._name)

    def _get_status(self):
        """Get the transfer and deletion status, if any"""
        # first get the transfer status
        self._get_transfer_status()

        # then get the deletion status
        self._get_deletion_status()

    def _get_deletion_status(self):
        """Checks for the deletion status, if one has been active"""
        if self._delete and self._deletion_id is not None:
            task_info = self._tc.get_task(self._deletion_id)

            # message
            msg = [f'[{self._name}]: Status of deletion with id {self._deletion_id}:']
            for key in STATUS_KEYS:
                msg.append(f"[{self._name}]:   {key}: {task_info[key]}")
            self._msg.extend(msg)
            self._msg.append("")

            if task_info["status"] == "FAILED":
                # print everything if failed
                self._logger.warning("Deletion failed!")
                for key in task_info.data.keys():
                    self._logger.warning(f"  {key}: {task_info[key]}")
            else:
                for line in msg:
                    self._logger.info(line)

            # if the deletion is finished, then remove the id
            if task_info["status"] in TRANSFER_FINISHED_STATUS:
                self._deletion_id = None

    def _delete_source(self):
        """Delete files from the source share."""
        self._logger.info("Deleting source files")

        # create the delete data object
        ddata = globus_sdk.DeleteData(self._tc, self._src_endpoint, recursive=True)

        # get list of files and directories under the shared directory
        # (we can't just delete the whole src_path because it could be the root (/) of the share and that will fail)
        count_delete = 0
        for entry in self._tc.operation_ls(self._src_endpoint, path=self._src_path):
            dpath = os.path.join(self._src_path, entry['name'])
            self._logger.debug(f"Adding for deletion: {dpath}")
            ddata.add_item(dpath)
            count_delete += 1

        if count_delete > 0:
            # submit the deletion
            delete_result = self._tc.submit_delete(ddata)
            self._deletion_id = delete_result['task_id']
            self._logger.debug(f"deletion id: {self._transfer_id}")
            self._msg.append(f"[{self._name}]: Deletion started with id: {self._deletion_id}")
        else:
            self._logger.debug("Nothing to delete")

    def _get_transfer_status(self):
        """Checks for an active transfer, reports info"""
        if self._transfer_id is not None:
            # info about transfer
            task_info = self._tc.get_task(self._transfer_id)

            # message
            msg = [f'[{self._name}]: Status of transfer with id {self._transfer_id}:']
            for key in STATUS_KEYS:
                msg.append(f"[{self._name}]:   {key}: {task_info[key]}")
            self._msg.extend(msg)
            self._msg.append("")

            # print to standard output
            if task_info["status"] == "FAILED" or (task_info["is_ok"] is not None and not task_info["is_ok"]):
                # print everything if failed
                self._logger.warning("Transfer failed!")
                for key in task_info.data.keys():
                    self._logger.warning(f"  {key}: {task_info[key]}")
            else:
                for line in msg:
                    self._logger.info(line)

            # if successful
            if task_info["status"] == "SUCCEEDED":
                # we send an email the first time the transfer succeeded, or if more files were transferred later
                if self._email is not None and (task_info["files_transferred"] > 0 or not self._sent_success_email):
                    self._send_email(task_info)
                    self._sent_success_email = True

                # start a deletion job
                if self._delete:
                    self._delete_source()

            # if the transfer is finished, then remove the id
            if task_info["status"] in TRANSFER_FINISHED_STATUS:
                self._transfer_id = None

    def _send_email(self, task_info):
        """Send email if successful and files were transferred"""
        self._logger.debug(f"Creating email to send to: {self._email}")
        subject = f"[Globus Sync Directory] {self._name} transfer complete"

        url_string = 'https://app.globus.org/file-manager?' + \
            urllib.parse.urlencode({
                'origin_id': self._dst_endpoint,
                'origin_path': self._dst_path,
            })

        def nice_size(size_bytes):
            units = ["B", "KB", "MB", "GB", "TB", "PB"]
            size = size_bytes
            size_unit = units.pop(0)
            while size >= 1024 and len(units):
                size /= 1024
                size_unit = units.pop(0)
            return f"{size:.3f} {size_unit}"

        msg = [
            f"Source endpoint: {task_info['source_endpoint_display_name']}",
            f"Source path: {self._src_path}",
            f"Destination endpoint: {task_info['destination_endpoint_display_name']}",
            f"Destination path: {self._src_path}",
            f"Status: {task_info['status']}",
            f"Number of directories: {task_info['directories']}",
            f"Files transferred: {task_info['files_transferred']}",
            f"Amount transferred: {nice_size(task_info['bytes_transferred'])}",
            f"View transferred files here: {url_string}",
        ]
        self._logger.debug("Sending email:\n" + "\n".join(msg))
        email.send_email(self._email.split(","), subject, "\n".join(msg))

    def get_msg(self):
        """Return the message"""
        return self._msg

    def process(self, start=True):
        """Process the transfer or print status if already active"""
        self._logger.info(f"Processing: {self._name}")

        # if there was an id stored in the cache, check if it is active
        self._msg = [f"[{self._name}]: Checking status of current transfer (if any)..."]
        self._get_status()

        # start a new transfer if:
        #  - there isn't a transfer already running
        #  - there isn't a deletion already running
        #  - command line options allow us to
        if self._transfer_id is None and self._deletion_id is None and start:
            # start a new transfer
            self._msg.append(f"[{self._name}]: Starting new transfer...")
            self._transfer()

            # check status of newly started transfer
            self._msg.append(f"[{self._name}]: Checking status of started transfer...")
            self._get_status()

    def _transfer(self):
        """Start the transfer"""
        # initiate the data transfer to NeSI
        tdata = globus_sdk.TransferData(
            self._tc,
            self._src_endpoint,
            self._dst_endpoint,
            label=f"Syncing data for {self._name}",
            sync_level=self._sync_level,
            deadline=self._deadline,
        )

        # add the directory to the transfer
        tdata.add_item(self._src_path, self._dst_path, recursive=True)

        # actually start the transfer
        transfer_result = self._tc.submit_transfer(tdata)
        self._transfer_id = transfer_result["task_id"]
        self._logger.info(f"transfer id: {self._transfer_id}")
        self._msg.append(f"[{self._name}]: Transfer started with id: {self._transfer_id}")

        # print url for viewing changes
        url_string = 'https://app.globus.org/file-manager?' + \
            urllib.parse.urlencode({
                'origin_id': self._src_endpoint,
                'origin_path': self._src_path,
                'destination_id': self._dst_endpoint,
                'destination_path': self._dst_path,
            })
        self._logger.info('Visit the link below to see the changes:\n{}'.format(url_string))
        self._msg.append(f"[{self._name}]: Visit the link below to see the changes:\n{url_string}")
        self._msg.append("")
