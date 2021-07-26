# Globus sync directory

Synchronise a directory between two Globus shared collections. Files and
directories will be synchronised from the specified directory on the source
endpoint to the destination endpoint.

```
GlobusSharedCollection
│
└───folderToBeSynced001
│   │   file011.txt
│   │   file012.txt
│   │
│   └───subfolder1
│       │   file111.txt
│       │   file112.txt
│       │   ...
│   
└───folderToBeSynced002
    │   file021.txt
    │   file022.txt
```

* Files will only be copied if they do not already exist on the destination
  endpoint or if their checksums do not match (i.e. they were modified on the
  source endpoint)
* Files removed from the source collection will not be removed from the
  destination collection if they already exist there.
* No files will be changed on the source endpoint (read-only access required)
* Transfers can be stopped and resumed later (using checksums)

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
3. Store the client id in the config file in the *app* section, named *clientid*
4. Store the secret in a file somewhere secure, e.g. *~/.globus_sync_directory_secret*

### For each directory you want to synchronise

Create source and destination shared globus collections

1. Locate the directory of the shared collection in the Globus file manager on
   your endpoint (this will be the directory that contains the directories to
   be synchronised as subdirectories): [https://app.globus.org/file-manager](https://app.globus.org/file-manager)
2. Share the collections with the app we created above: *<CLIENT_ID>@clients.auth.globus.org*
3. Put the collection endpoint ids and path to the directory to share within the src collection into the config file

## Running

TODO
