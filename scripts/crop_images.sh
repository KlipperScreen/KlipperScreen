#!/bin/bash

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
IMGDIR=$SCRIPTPATH/../docs/img

for file in $IMGDIR/*
do
    res=$(identify $file | cut -d ' ' -f 3)
    if [ "$res" != "1532x898" ]; then
        echo "Converting $file"
        convert $file -crop 1532x898+2+48 $file
    fi
done
