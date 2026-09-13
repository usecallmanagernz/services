#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import traceback

from flask import Blueprint, Response, request

import config


blueprint = Blueprint('authentication', __name__)


@blueprint.route('/authentication')
def cgi_authentication():
    username = request.args.get('UserID', '')
    password = request.args.get('Password', '')

    if username != config.cgi_username or password != config.cgi_password:
        return Response('UNAUTHORIZED', headers = {'Content-Type': 'text/plain'}), 200

    return Response('AUTHORIZED', headers = {'Content-Type': 'text/plain'}), 200


@blueprint.errorhandler(Exception)
def error_handler(error):
    traceback.print_exc(file = sys.stderr)

    return Response('ERROR', headers = {'Content-Type': 'text/plain'}), 500
