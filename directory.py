#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import re
from math import ceil
from urllib.parse import quote_plus
from html import escape

import requests
from lxml import etree
from flask import Blueprint, Response, request, g
import config


blueprint = Blueprint('directory', __name__)


@blueprint.route('/directory')
def directory_index():
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneMenu>\n'
           '  <Title>Local Directory</Title>\n')

    for index in ('1', '2ABC', '3DEF', '4GHI', '5JKL', '6MNO', '7PRQS', '8TUV', '9WXYZ', '0'):
        xml += ('  <MenuItem>\n'
                '    <Name>' + escape(index) + '</Name>\n'
                '    <URL>' + request.url_root + 'directory/entries?index=' + quote_plus(index) + '</URL>\n'
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


@blueprint.route('/directory/entries')
def directory_entries():
    index = request.args.get('index', '')

    if not len(index):
        return directory_index()

    session = requests.Session()

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'Login',
                                                                      'Username': config.manager_username,
                                                                      'Secret': config.manager_secret})
    response.raise_for_status()

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'VoicemailUsersList'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    entries = []

    for element in document.findall('response/generic[@event="VoicemailUserEntry"]'):
        mailbox = element.get('voicemailbox')
        name = element.get('fullname', '')

        if name[0].upper() not in index:
            continue

        entries.append((mailbox, name))

    entries.sort(key = lambda entry: entry[1])

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'Logoff'})
    response.raise_for_status()

    # 10 entries per page
    pages = ceil(len(entries) / 10)

    try:
        page = int(request.args.get('page', '1'))

        if page > pages:
            raise ValueError

    except ValueError:
        page = 1

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneDirectory>\n'
           '  <Title>' + escape(index) + (' ' + str(page) + '/' + str(pages) if pages > 1 else '') + '</Title>\n')

    for mailbox, name in entries[(page - 1) * 10:page * 10]:
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
                '    <URL>' + request.url_root + 'directory/entries?index=' + quote_plus(index) + '&amp;page=' + str(page + 1) + '</URL>\n'
                '    <Position>' + ('2' if g.is_79xx else '3') + '</Position>\n'
                '  </SoftKeyItem>\n')

    if page > 1:
        xml += ('  <SoftKeyItem>\n'
                '    <Name>Previous</Name>\n'
                '    <URL>' + request.url_root + 'directory/entries?index=' + quote_plus(index) + '&amp;page=' + str(page - 1) + '</URL>\n'
                '    <Position>' + ('4' if g.is_79xx else '4') + '</Position>\n'
                '  </SoftKeyItem>\n')

    xml += '</CiscoIPPhoneDirectory>\n'

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/directory/help')
def directory_help():
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
def directory_menuitem():
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
    g.is_79xx = re.search(r'(?x) ^ CP-79', request.headers.get('X-CiscoIPPhoneModelName', ''))


@blueprint.errorhandler(Exception)
def error_handler(error):
    return Response(str(error), mimetype = 'text/plain'), 500
