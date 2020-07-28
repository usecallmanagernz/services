#!/usr/bin/python3

import os.path
import re
from math import ceil
from urllib.parse import quote_plus
from html import escape
from lxml import etree
import requests
from flask import Blueprint, Response, request, g
import config


blueprint = Blueprint('directory', __name__)


@blueprint.route('/directory')
def directory_index():
    content = '<?xml version="1.0" encoding="UTF-8"?>' \
        '<CiscoIPPhoneMenu>' \
          '<Title>Local Directory</Title>'

    for index in ('1', '2ABC', '3DEF', '4GHI', '5JKL', '6MNO', '7PRQS', '8TUV', '9WXYZ', '0'):
        content += '<MenuItem>' \
            '<Name>' + escape(index) + '</Name>' \
            '<URL>' + request.url_root + 'directory/entries?name=' + quote_plus(g.device_name) + '&amp;index=' + quote_plus(index) + '</URL>' \
          '</MenuItem>'

    if g.is_79xx:
        content += '<Prompt>Your current options</Prompt>'

    content += '<SoftKeyItem>' \
            '<Name>Exit</Name>' \
            '<Position>' + ('3' if g.is_79xx else '1') + '</Position>' \
            '<URL>Init:Directories</URL>' \
          '</SoftKeyItem>' \
          '<SoftKeyItem>' \
            '<Name>' + ('Select' if g.is_79xx else 'View') + '</Name>' \
            '<Position>' + ('1' if g.is_79xx else '2') + '</Position>' \
            '<URL>SoftKey:Select</URL>' \
          '</SoftKeyItem>' \
          '<SoftKeyItem>' \
            '<Name>Help</Name>' \
            '<Position>' + ('2' if g.is_79xx else '3') + '</Position>' \
            '<URL>' + request.url_root + 'directory/help?name=' + quote_plus(g.device_name) + '</URL>' \
          '</SoftKeyItem>' \
        '</CiscoIPPhoneMenu>'

    return Response(content, mimetype = 'text/xml'), 200


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
        extension = element.get('voicemailbox')
        name = element.get('fullname', '')

        if name[0].upper() not in index:
            continue

        entries.append((extension, name))

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

    content = '<?xml version="1.0" encoding="UTF-8"?>' \
        '<CiscoIPPhoneDirectory>' \
          '<Title>' + escape(index) + (' ' + str(page) + '/' + str(pages) if pages > 1 else '') + '</Title>'

    for extension, name in entries[(page - 1) * 10:page * 10]:
        content += '<DirectoryEntry>' \
              '<Name>' + escape(name) + '</Name>' \
              '<Telephone>' + quote_plus(extension) + '</Telephone>' \
            '</DirectoryEntry>'

    if g.is_79xx:
        content += '<Prompt>Select entry</Prompt>'

    content += '<SoftKeyItem>' \
          '<Name>Exit</Name>' \
          '<Position>' + ('3' if g.is_79xx else '1') + '</Position>' \
          '<URL>' + request.url_root + 'directory?name=' + quote_plus(g.device_name) + '</URL>' \
        '</SoftKeyItem>' \
        '<SoftKeyItem>' \
          '<Name>' + ('Dial' if g.is_79xx else 'Call') + '</Name>' \
          '<Position>' + ('1' if g.is_79xx else '2') + '</Position>' \
          '<URL>SoftKey:Select</URL>' \
        '</SoftKeyItem>'

    if page < pages:
        content += '<SoftKeyItem>' \
              '<Name>Next</Name>' \
              '<URL>' + request.url_root + 'directory/entries?name=' + quote_plus(g.device_name) + '&amp;index=' + quote_plus(index) + '&amp;page=' + str(page + 1) + '</URL>' \
              '<Position>' + ('2' if g.is_79xx else '3') + '</Position>' \
            '</SoftKeyItem>'

    if page > 1:
        content += '<SoftKeyItem>' \
              '<Name>Previous</Name>' \
              '<URL>' + request.url_root + 'directory/entries?name=' + quote_plus(g.device_name) + '&amp;index=' + quote_plus(index) + '&amp;page=' + str(page - 1) + '</URL>' \
              '<Position>' + ('4' if g.is_79xx else '4') + '</Position>' \
            '</SoftKeyItem>'

    content += '</CiscoIPPhoneDirectory>'

    return Response(content, mimetype = 'text/xml'), 200


@blueprint.route('/directory/help')
def directory_help():
    content = '<?xml version="1.0" encoding="UTF-8"?>' \
        '<CiscoIPPhoneText>' \
          '<Title>How To Use</Title>' \
          '<Text>Use the keypad or navigation key to select the first letter of the person\'s name.</Text>'

    if g.is_79xx:
        content += '<Prompt>Your current options</Prompt>'

    content += '<SoftKeyItem>' \
            '<Name>Back</Name>' \
            '<URL>SoftKey:Exit</URL>' \
            '<Position>' + ('3' if g.is_79xx else '1') + '</Position>' \
          '</SoftKeyItem>' \
        '</CiscoIPPhoneText>'

    return Response(content, mimetype = 'text/xml'), 200


@blueprint.route('/directory/79xx')
def directory_menuitem():
    # 79xx series need a menu item before the index
    content = '<?xml version="1.0" encoding="UTF-8"?>' \
        '<CiscoIPPhoneMenu>' \
          '<MenuItem>' \
            '<Name>Local Directory</Name>' \
            '<URL>' + request.url_root + 'directory?name=' + quote_plus(g.device_name) + '</URL>' \
          '</MenuItem>' \
        '</CiscoIPPhoneMenu>'

    return Response(content, mimetype = 'text/xml'), 200


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
