#!/usr/bin/python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import os.path
import re

from flask import Blueprint, Response, request, g
import config


blueprint = Blueprint('authentication', __name__)


@blueprint.route('/authentication')
def cgi_authentication():
    username = request.args.get('UserID', '')
    password = request.args.get('Password', '')

    if username != config.cgi_username or password != config.cgi_password:
        return Response('UNAUTHORIZED', mimetype = 'text/plain'), 200

    return Response('AUTHORIZED', mimetype = 'text/plain'), 200


@blueprint.before_request
def before_request():
    device_name = request.args.get('devicename', '')

    # check that the device name is valid
    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name) or \
       not os.path.exists(f'{config.tftpboot_dir}/{device_name}.cnf.xml'):
        return Response('ERROR'), 403

    g.device_name = device_name

    return None


@blueprint.errorhandler(Exception)
def error_handler(error):
    return Response('ERROR', mimetype = 'text/plain'), 500
