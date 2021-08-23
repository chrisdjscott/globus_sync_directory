# Globus sync directory

Synchronise directories between Globus shared collections. Files and
directories will be synchronised from the specified directory on the source
endpoint to the destination endpoint. Multiple source and destination
endpoints can be specified.

```
GlobusSharedCollection
│
└───dirtoshare
    │   file011.txt
    │   file012.txt
    │
    └───subfolder1
        │   file111.txt
        │   file112.txt
        │   ...
```

* Files will only be copied if they do not already exist on the destination
  endpoint or if their checksums do not match (i.e. they were modified on the
  source endpoint)
* Files removed from the source collection will not be removed from the
  destination collection if they already exist there
* No files will be changed on the source endpoint (read-only access required)
* Transfers can be stopped and resumed later (using checksums), e.g. by
  setting a time limit in the config file

## Requirements

### Register the app with Globus (one time setup)

We are using [client credentials authentication](https://globus-sdk-python.readthedocs.io/en/stable/examples/client_credentials.html) to authenticate the app directly with Globus.

1. You must register the app and get a Client ID: https://globus-sdk-python.readthedocs.io/en/stable/examples/client_credentials.html#get-a-client
   1. Go to [developers.globus.org](https://developers.globus.org/)
   2. Click *Register your app with Globus*
   3. Click *Add another project*, give it a project name, e.g. *Sync Directory* and enter a contact email
   4. On the project, click *Add* and *Add new app*
      * Give the app a name, e.g. *Sync Directory App*
      * Make sure *Native App* is **not** selected
      * Enter the following scopes: 
        - openid
        - profile
        - email
        - urn:globus:auth:scope:transfer.api.globus.org:all
      * Add the following redirect: https://localhost
      * Create the app
   5. Make a note of the *Client ID*
   6. Click *Generate New Client Secret* and make a note of the secret
3. Store the client id in the config file in the *globus* section, named *clientid*
4. Store the secret in a file somewhere secure, e.g. *~/.globus_sync_directory_secret*
5. If you are using a personal endpoint, make sure sharing is enabled (Preferences -> Access -> Shareable)

### For each directory you want to synchronise

Create source and destination shared globus collections

**Note**: if creating an endpoint on a Globus personal endpoint, make sure you
have enabled sharing for that endpoint in the Globus personal endpoint
settings/preferences.

1. Locate the directory of the shared collection in the Globus file manager on
   your endpoint (this will be the directory that contains the directories to
   be synchronised as subdirectories): [https://app.globus.org/file-manager](https://app.globus.org/file-manager)
2. Share the collections with the app we created above: *<CLIENT_ID>@clients.auth.globus.org*
3. Put the collection endpoint ids and path to the directory to share within the src collection into the config file

## Running on NeSI

You could automate running the sync via `scrontab` on NeSI using the wrapper script provided and the following steps.

1. Open a terminal (e.g. via https://jupyter.nesi.org.nz) and clone this repo somewhere, e.g.
   ```
   git clone https://github.com/chrisdjscott/globus_sync_directory.git ~/globus_sync_directory
   ```
2. Create a config file and edit it:
   ```
   cd ~/globus_sync_directory
   cp config.ini.example config.ini
   # edit config.ini
   ```
3. Load a Python module:
   ```
   ml purge
   ml Python/3.8.2-gimkl-2020a
   ```
5. Create a virtual environment and install this package:
   ```
   python -m venv venv
   source venv/bin/activate
   python setup.py install
   ```
6. Open your scrontab:
   ```
   export EDITOR=nano  # set your favourite editor
   scrontab
   ```
7. Add the following lines, which will start the sync at midnight NZ time daily (note times in `scrontab` are in UTC, so the 12 belows specifies midnight UTC) and follow up with a status update at 7am (19:00 UTC, the `-d` argument means don't start a new transfer, just print the status of the current/last transfer):
   ```
   #SCRON -t 05:00
   0 12 * * * $HOME/globus_sync_directory/nesi_sync_directory_wrapper.sh
   
   #SCRON -t 05:00
   0 19 * * * $HOME/globus_sync_directory/nesi_sync_directory_wrapper.sh -d
   ```
8. Your scheduled cron job should show up in the Slurm queue: `squeue -u $USER`
   - Output from the jobs will show up in: *~/globus_sync_directory/globus_sync_directory.log*
   - You can query the state of the most recent job, if any, by running: `python -m globus_sync_directory -d` from the repo directory
