#!/usr/bin/python3

import os.path
import re
from datetime import datetime
from flask import Blueprint, Response, request, g
import config


blueprint = Blueprint('problem_report', __name__)


@blueprint.route('/problem-report', methods = ['POST'])
def problem_report():
    prt_file = request.files.get('prt_file')

    if prt_file is None:
        return Response('Missing problem report', mimetype = 'text/plain'), 500

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    prt_file.save(f'{config.reports_dir}/{g.device_name}-{timestamp}.tar.gz')

    return Response('Log saved', mimetype = 'text/plain'), 200


@blueprint.before_request
def before_request():
    device_name = request.form.get('devicename', '')

    if not re.search(r'(?x) SEP [0-9A-F]{12} $', device_name) or \
       not os.path.exists(f'{config.tftpboot_dir}/{device_name}.cnf.xml'):
        return Response('Invalid device', mimetype = 'text/plain'), 403

    g.device_name = device_name

    return None


@blueprint.errorhandler(Exception)
def error_handler(error):
    return Response(str(error), mimetype = 'text/plain'), 500
