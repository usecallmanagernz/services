#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import os
import re
import traceback
from datetime import datetime

from flask import Blueprint, Response, request

import config


blueprint = Blueprint('problem_report', __name__)


@blueprint.route('/problem-report', methods = ['POST'])
def save_report():
    # Newer firmware now puts a leading newline for multipart/form-data variables
    device_name = request.form.get('devicename', '').strip()

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name):
        return Response('Invalid device', headers = {'Content-Type': 'text/plain'}), 403

    prt_file = request.files.get('prt_file')

    if prt_file is None:
        return Response('Missing problem report', headers = {'Content-Type': 'text/plain'}), 500

    if not os.path.exists(config.reports_dir):
        return Response('Invalid reports directory', headers = {'Content-Type': 'text/plain'}), 500

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    prt_file.save(f'{config.reports_dir}/prt-{device_name}-{timestamp}.tar.gz')

    return Response('Log saved', headers = {'Content-Type': 'text/plain'}), 200


@blueprint.errorhandler(Exception)
def error_handler(error):
    traceback.print_exc(file = sys.stderr)

    return Response(str(error), headers = {'Content-Type': 'text/plain'}), 500
