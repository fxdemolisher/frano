#!/bin/bash
#
# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.
#

FRANO_PATH=/var/lib/django/frano
PYTHON_PATH=/usr/bin/python

echo "--------------------" `date` "--------------------"
cd $FRANO_PATH
$PYTHON_PATH manage.py $@
