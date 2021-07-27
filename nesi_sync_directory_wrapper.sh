#!/bin/bash -e

# change to directory containing this script
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
cd $SCRIPT_DIR

# load Python module
ml purge > /dev/null 2>&1
ml Python/3.8.2-gimkl-2020a

# run the script
python globus_sync_directory.py >> globus_sync_directory.log 2>&1
