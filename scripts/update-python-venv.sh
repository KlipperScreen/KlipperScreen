#!/bin/bash

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
KSPATH=$(sed 's/\/scripts//g' <<< $SCRIPTPATH)
KSENV="${HOME}/.KlipperScreen-env"

update_virtualenv()
{
    echo "Creating virtual environment"
    [ ! -d ${KSENV} ] && virtualenv -p /usr/bin/python3 ${KSENV}

    ${KSENV}/bin/pip install -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
    ${KSENV}/bin/pip install --no-binary ":all" "vext.gi==0.7.4"
    ${KSENV}/bin/vext -e
}

update_virtualenv
