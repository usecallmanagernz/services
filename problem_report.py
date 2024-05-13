#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import re
from datetime import datetime

from flask import Blueprint, Response, request
import config


blueprint = Blueprint('problem_report', __name__)


@blueprint.route('/problem-report', methods = ['POST'])
def problem_report():
    device_name = request.form.get('devicename', '')

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name):
        return Response('Invalid device', mimetype = 'text/plain'), 403

    prt_file = request.files.get('prt_file')

    if prt_file is None:
        return Response('Missing problem report', mimetype = 'text/plain'), 500

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    prt_file.save(f'{config.reports_dir}/{device_name}-{timestamp}.tar.gz')

    return Response('Log saved', mimetype = 'text/plain'), 200


@blueprint.errorhandler(Exception)
def error_handler(error):
    return Response(str(error), mimetype = 'text/plain'), 500
