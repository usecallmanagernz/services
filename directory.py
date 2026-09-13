#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import re
import traceback
from math import ceil

import requests
from lxml import etree
from lxml.builder import E as tag
from flask import Blueprint, Response, request, g as context

import config


blueprint = Blueprint('directory', __name__)


@blueprint.route('/directory')
def application_menu():
    if not context.is_79xx:
        return list_directories()

    # 79xx series needs a menu item first
    document = tag('CiscoIPPhoneMenu',
        tag('MenuItem',
            tag('Name', 'Local Directory'),
            tag('URL', request.url_root + 'directory/menu')
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/directory/menu')
def list_directories():
    document = tag('CiscoIPPhoneMenu', tag('Title', 'Local Directory' if context.is_79xx else 'Contacts'))

    for index in ('1', '2ABC', '3DEF', '4GHI', '5JKL', '6MNO', '7PRQS', '8TUV', '9WXYZ', '0'):
        document.append(tag('MenuItem',
            tag('Name', index),
            tag('URL', request.url_root + 'directory/' + index)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Exit'),
            tag('URL', 'Init:Directories'),
            tag('Position', '3' if context.is_79xx else '1')
        ),
        tag('SoftKeyItem',
            tag('Name', 'Select' if context.is_79xx else 'View'),
            tag('URL', 'SoftKey:Select'),
            tag('Position', '1' if context.is_79xx else '2')
        ),
        tag('SoftKeyItem',
            tag('Name', 'Help'),
            tag('URL', request.url_root + 'directory/help'),
            tag('Position', '2' if context.is_79xx else '3')
        )
    ])

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/directory/<index>')
def list_mailboxes(index):
    if not re.search(r'(?x) ^ [A-Z0-9]+ $', index):
        return list_directories()

    response = context.session.get(config.manager_url, timeout = 5, params = {'Action': 'VoicemailUsersList'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    mailboxes = []

    for element in document.findall('response/generic[@event="VoicemailUserEntry"]'):
        mailbox = element.get('voicemailbox')
        name = element.get('fullname', '')

        if not len(name) or name[0].upper() not in index:
            continue

        mailboxes.append((mailbox, name))

    mailboxes.sort(key = lambda mailbox: mailbox[1])
    pages = ceil(len(mailboxes) / 10)

    try:
        page = int(request.args.get('page', '1'))

        if page < 1 or page > pages:
            raise ValueError

    except ValueError:
        page = 1

    document = tag('CiscoIPPhoneDirectory', tag('Title', index + (' ' + str(page) + '/' + str(pages) if pages > 1 else '')))

    for mailbox, name in mailboxes[(page - 1) * 10:page * 10]:
        document.append(tag('DirectoryEntry',
            tag('Name', name),
            tag('Telephone', mailbox)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 5)))

    document.append(tag('SoftKeyItem',
        tag('Name', 'Back' if context.is_79xx else 'Exit'),
        tag('URL', request.url_root + 'directory/menu' if context.is_79xx else 'Init:Directories'),
        tag('Position', '3' if context.is_79xx else next(position))
    ))

    document.append(tag('SoftKeyItem',
        tag('Name', 'Dial' if context.is_79xx else 'Call'),
        tag('URL', 'SoftKey:Select'),
        tag('Position', '1' if context.is_79xx else next(position))
    ))

    if page < pages:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Next'),
            tag('URL', request.url_root + 'directory/' + index + '?page=' + str(page + 1)),
            tag('Position', '2' if context.is_79xx else next(position))
        ))

    if page > 1:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Previous'),
            tag('URL', request.url_root + 'directory/' + index + '?page=' + str(page - 1)),
            tag('Position', '2' if context.is_79xx else next(position))
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/directory/help')
def help_message():
    document = tag('CiscoIPPhoneText',
        tag('Title', 'How To Use'),
        tag('Text', 'Use the keypad or navigation key to select the first letter of the person\'s name.'))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    document.append(tag('SoftKeyItem',
        tag('Name', 'Back' if context.is_79xx else 'Exit'),
        tag('URL', request.url_root + 'directory/menu'),
        tag('Position', '3' if context.is_79xx else '1')
    ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.before_request
def before_request():
    context.session = requests.Session()

    response = context.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'Login',
        'Username': config.manager_username,
        'Secret': config.manager_secret
    })
    response.raise_for_status()

    context.is_79xx = re.search(r'(?x) ^ CP-79', request.headers.get('X-CiscoIPPhoneModelName', ''))


@blueprint.teardown_request
def teardown_request(exception = None):
    if not exception and "mansession_id" in context.session.cookies:
        context.session.get(config.manager_url, timeout = 5, params = {'Action': 'Logoff'})


@blueprint.errorhandler(Exception)
def error_handler(error):
    traceback.print_exc(file = sys.stderr)

    return Response(str(error), headers = {'Content-Type': 'text/plain'}), 500
