#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

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
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneMenu>\n'
           '  <Title>Services</Title>\n'
           '    <MenuItem>\n'
           '    <Name>Parked Calls</Name>\n'
           '    <URL>' + request.url_root + 'services/parked-calls</URL>\n'
           '  </MenuItem>\n')

    if g.is_79xx:
        xml += '  <Prompt>Your current options</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '    <URL>Init:Services</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Select</Name>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '    <URL>SoftKey:Select</URL>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneMenu>\n')

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

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneDirectory>\n'
           '  <Title>Parked Calls</Title>\n')

    for extension, name in calls:
        xml += ('<DirectoryEntry>\n'
                '  <Name>' + escape(name) + '</Name>\n'
                '  <Telephone>' + quote_plus(extension) + '</Telephone>\n'
                '</DirectoryEntry>\n')

    if g.is_79xx:
        xml += '  <Prompt>Select call</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '    <URL>' + request.url_root + 'services</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>' + ('Dial' if g.is_79xx else 'Call') + '</Name>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '    <URL>SoftKey:Select</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Update</Name>\n'
            '    <Position>' + ('2' if g.is_79xx else '3') + '</Position>\n'
            '    <URL>SoftKey:Update</URL>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneDirectory>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.before_request
def before_request():
    g.is_79xx = re.search(r'(?x) ^ CP-79', request.headers.get('X-CiscoIPPhoneModelName', ''))


@blueprint.errorhandler(Exception)
def error_handler(error):
    return Response(str(error), mimetype = 'text/plain'), 500
