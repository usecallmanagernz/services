#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import re
import traceback
from math import ceil
from urllib.parse import quote_plus
from html import escape

import requests
from lxml import etree
from flask import Blueprint, Response, request, g

import config


blueprint = Blueprint('directory', __name__)


@blueprint.route('/directory')
def get_index():
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneMenu>\n'
           '  <Title>Local Directory</Title>\n')

    for index in ('1', '2ABC', '3DEF', '4GHI', '5JKL', '6MNO', '7PRQS', '8TUV', '9WXYZ', '0'):
        xml += ('  <MenuItem>\n'
                '    <Name>' + escape(index) + '</Name>\n'
                '    <URL>' + request.url_root + 'directory/mailboxes/' + quote_plus(index) + '</URL>\n'
                '  </MenuItem>\n')

    if g.is_79xx:
        xml += '  <Prompt>Your current options</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '    <URL>Init:Directories</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>' + ('Select' if g.is_79xx else 'View') + '</Name>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '    <URL>SoftKey:Select</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Help</Name>\n'
            '    <Position>' + ('2' if g.is_79xx else '3') + '</Position>\n'
            '    <URL>' + request.url_root + 'directory/help</URL>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneMenu>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/directory/mailboxes/<index>')
def list_mailboxes(index):
    if not re.search(r'(?x) ^ [A-Z0-9]+ $', index):
        return directory_index()

    response = g.session.get(config.manager_url, timeout = 5, params = {'Action': 'VoicemailUsersList'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    mailboxes = []

    for element in document.findall('response/generic[@event="VoicemailUserEntry"]'):
        mailbox = element.get('voicemailbox')
        name = element.get('fullname', '')

        if not len(name) or name[0].upper() not in index:
            continue

        mailboxes.append((mailbox, name))

    mailboxes.sort(key = lambda mailbox: mailbox[1])

    # 10 mailboxes per page
    pages = ceil(len(mailboxes) / 10)

    try:
        page = int(request.args.get('page', '1'))

        if page > pages:
            raise ValueError

    except ValueError:
        page = 1

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneDirectory>\n'
           '  <Title>' + escape(index) + (f' {page}/{pages}' if pages > 1 else '') + '</Title>\n')

    for mailbox, name in mailboxes[(page - 1) * 10:page * 10]:
        xml += ('  <DirectoryEntry>\n'
                '    <Name>' + escape(name) + '</Name>\n'
                '    <Telephone>' + quote_plus(mailbox) + '</Telephone>\n'
                '  </DirectoryEntry>\n')

    if g.is_79xx:
        xml += '  <Prompt>Select entry</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '    <URL>' + request.url_root + 'directory</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>' + ('Dial' if g.is_79xx else 'Call') + '</Name>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '    <URL>SoftKey:Select</URL>\n'
            '  </SoftKeyItem>\n')

    if page < pages:
        xml += ('  <SoftKeyItem>\n'
                '    <Name>Next</Name>\n'
                '    <URL>' + request.url_root + 'directory/mailboxes/' + quote_plus(index) + f'?page={page + 1}' + '</URL>\n'
                '    <Position>' + ('2' if g.is_79xx else '3') + '</Position>\n'
                '  </SoftKeyItem>\n')

    if page > 1:
        xml += ('  <SoftKeyItem>\n'
                '    <Name>Previous</Name>\n'
                '    <URL>' + request.url_root + 'directory/mailboxes/' + quote_plus(index) + f'?page={page - 1}' + '</URL>\n'
                '    <Position>' + ('4' if g.is_79xx else '4') + '</Position>\n'
                '  </SoftKeyItem>\n')

    xml += '</CiscoIPPhoneDirectory>\n'

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/directory/help')
def help_message():
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneText>\n'
           '  <Title>How To Use</Title>\n'
           '  <Text>Use the keypad or navigation key to select the first letter of the person\'s name.</Text>\n')

    if g.is_79xx:
        xml += '  <Prompt>Your current options</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Back</Name>\n'
            '    <URL>SoftKey:Exit</URL>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneText>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/directory/79xx')
def menu_item():
    # 79xx series need a menu item before the index
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneMenu>\n'
           '  <MenuItem>\n'
           '    <Name>Local Directory</Name>\n'
           '    <URL>' + request.url_root + 'directory</URL>\n'
           '  </MenuItem>\n'
           '</CiscoIPPhoneMenu>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.before_request
def before_request():
    g.session = requests.Session()

    response = g.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'Login',
        'Username': config.manager_username,
        'Secret': config.manager_secret
    })
    response.raise_for_status()

    g.is_79xx = re.search(r'(?x) ^ CP-79', request.headers.get('X-CiscoIPPhoneModelName', ''))


@blueprint.teardown_request
def teardown_request(exception = None):
    if not exception and "mansession_id" in g.session.cookies:
        g.session.get(config.manager_url, timeout = 5, params = {'Action': 'Logoff'})


@blueprint.errorhandler(Exception)
def error_handler(error):
    traceback.print_exc(file = sys.stderr)

    return Response(str(error), mimetype = 'text/plain'), 500
