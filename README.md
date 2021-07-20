# Globus sync directory

Sync a directory between two Globus shared collections.

Files and directories will be recursively copied from the source endpoint to
the destination endpoint if they do not already exist on the destination
endpoint or if their checksum do not match. Files removed from the source
collection will not be removed from the destination collection if they already
exist there.

## Requirements

We are using [client credentials authentication](https://globus-sdk-python.readthedocs.io/en/stable/examples/client_credentials.html) to authenticate the app directly with Globus.

1. You must register the app and get a Client ID: https://globus-sdk-python.readthedocs.io/en/stable/examples/client_credentials.html#get-a-client
2. Store the client id in the config file
3. Store the secret in a file somewhere secure, e.g. *~/.globus_sync_directory.secret*
4. Create source and destination shared globus collections
5. Share the collections with the app we created above: *<CLIENT_ID>@clients.auth.globus.org*
6. Put the collection endpoint ids and path to the directory to share within the src collection into the config file

## TODO:

* option to specify multiple directories/endpoints to keep synced
* option not to wait for completion, e.g. cache transfer id and pick up on previous transfer if find a cached one (could be used with cron)
* remove files from src endpoint once they have been transferred?
* notification on completion?
