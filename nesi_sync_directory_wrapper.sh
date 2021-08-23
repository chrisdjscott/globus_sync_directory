#!/bin/bash -e

# change to directory containing this script
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
cd "$SCRIPT_DIR"

# load Python module
ml purge > /dev/null 2>&1
ml Python/3.8.2-gimkl-2020a

# load the virtual environment
export PYTHONNOUSERSITE=1
source venv/bin/activate

# run the script
sync_directory $@ >> globus_sync_directory.log 2>&1
