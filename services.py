#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import os.path
import re
from urllib.parse import quote_plus
from html import escape

import requests
from lxml import etree
from flask import Blueprint, Response, request, g
import config


blueprint = Blueprint('services', __name__)


@blueprint.route('/services')
def services_menu():
    xml = '<?xml version="1.0" encoding="UTF-8"?>' \
        '<CiscoIPPhoneMenu>' \
          '<Title>Services</Title>' \
          '<MenuItem>' \
            '<Name>Parked Calls</Name>' \
            '<URL>' + request.url_root + 'services/parked-calls?name=' + quote_plus(g.device_name) + '</URL>' \
          '</MenuItem>'

    if g.is_79xx:
        xml += '<Prompt>Your current options</Prompt>'

    xml += '<SoftKeyItem>' \
            '<Name>Exit</Name>' \
            '<Position>' + ('3' if g.is_79xx else '1') + '</Position>' \
            '<URL>Init:Services</URL>' \
          '</SoftKeyItem>' \
          '<SoftKeyItem>' \
            '<Name>Select</Name>' \
            '<Position>' + ('1' if g.is_79xx else '2') + '</Position>' \
            '<URL>SoftKey:Select</URL>' \
          '</SoftKeyItem>' \
        '</CiscoIPPhoneMenu>'

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/services/parked-calls')
def parked_calls():
    session = requests.Session()

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'Login',
                                                                      'Username': config.manager_username,
                                                                      'Secret': config.manager_secret})
    response.raise_for_status()

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'ParkedCalls'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    calls = []

    for element in document.findall('response/generic[@event="ParkedCall"]'):
        extension = element.get('exten')
        name = element.get('calleridname') or element.get('calleridnum')

        calls.append((extension, name))

    calls.sort(key = lambda call: call[0])

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'Logoff'})
    response.raise_for_status()

    xml = '<?xml version="1.0" encoding="UTF-8"?>' \
        '<CiscoIPPhoneDirectory>' \
          '<Title>Parked Calls</Title>'

    for extension, name in calls:
        xml += '<DirectoryEntry>' \
              '<Name>' + escape(name) + '</Name>' \
              '<Telephone>' + quote_plus(extension) + '</Telephone>' \
            '</DirectoryEntry>'

    if g.is_79xx:
        xml += '<Prompt>Select call</Prompt>'

    xml += '<SoftKeyItem>' \
            '<Name>Exit</Name>' \
            '<Position>' + ('3' if g.is_79xx else '1') + '</Position>' \
            '<URL>' + request.url_root + 'services?name=' + quote_plus(g.device_name) + '</URL>' \
          '</SoftKeyItem>' \
          '<SoftKeyItem>' \
            '<Name>' + ('Dial' if g.is_79xx else 'Call') + '</Name>' \
            '<Position>' + ('1' if g.is_79xx else '2') + '</Position>' \
            '<URL>SoftKey:Select</URL>' \
          '</SoftKeyItem>' \
          '<SoftKeyItem>' \
            '<Name>Update</Name>' \
            '<Position>' + ('2' if g.is_79xx else '3') + '</Position>' \
            '<URL>SoftKey:Update</URL>' \
          '</SoftKeyItem>' \
        '</CiscoIPPhoneDirectory>'

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.before_request
def before_request():
    device_name = request.args.get('name', '')

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name) or \
       not os.path.exists(f'{config.tftpboot_dir}/{device_name}.cnf.xml'):
        return Response('Invalid device', mimetype = 'text/plain'), 500

    g.device_name = device_name
    g.is_79xx = re.search(r'(?x) ^ CP-79', request.headers.get('X-CiscoIPPhoneModelName', ''))

    return None


@blueprint.errorhandler(Exception)
def error_handler(error):
    return Response(str(error), mimetype = 'text/plain'), 500
