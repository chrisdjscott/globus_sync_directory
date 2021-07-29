# Globus sync directory

Synchronise a directory between two Globus shared collections. Files and
directories will be synchronised from the specified directory on the source
endpoint to the destination endpoint.

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
3. Load a Python module
   ```
   ml purge
   ml Python/3.8.2-gimkl-2020a
   ```
5. Make sure the requirements are installed:
   ```
   pip install --user -r requirements.txt
   ```
6. Open your scrontab:
   ```
   export EDITOR=nano  # set your favourite editor
   scrontab
   ```
7. Add the following lines, which will run the sync at 7pm NZ time daily (note times in `scrontab` are in UTC, so the 7 belows specifies 7am UTC):
   ```
   #SCRON -t 05:00
   #SCRON --qos=debug
   0 7 * * * $HOME/globus_sync_directory/nesi_sync_directory_wrapper.sh
   ```
8. Your scheduled cron job should show up in the Slurm queue: `squeue -u $USER`
   - Output from the jobs will show up in: *~/globus_sync_directory/globus_sync_directory.log*
   - You can query the state of the most recent job, if any, by running: `python globus_sync_directory.py -d` from the repo directory
