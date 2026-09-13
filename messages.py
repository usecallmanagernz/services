#!/usr/bin/env python3
#
# Copyright (c) 2026 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import re
import traceback
from math import ceil
from datetime import datetime, timezone

import requests
from lxml import etree
from lxml.builder import E as tag
from flask import Blueprint, Response, request, g as context

import config


FOLDER_NAMES = ('INBOX', 'Old', 'Urgent', 'Work', 'Friends', 'Family', 'Deleted')
GREETING_NAMES = ('Name', 'Unavailable', 'Busy', 'Temporary')

blueprint = Blueprint('messages', __name__)


@blueprint.route('/messages')
def get_mailbox():
    device_name = request.args.get('name', '')

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name):
        return Response('Invalid device', headers = {'Content-Type': 'text/plain'}), 403

    response = context.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'SIPShowPeer',
        'DeviceName': device_name
    })
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    element = document.find('response/generic[@response="Success"]')

    if element is None:
        return Response('Unknown device', headers = {'Content-Type': 'text/plain'}), 404

    mailbox, _ = element.get('mailbox', '').split('@', maxsplit = 1)

    if not len(mailbox):
        return Response('No mailbox', headers = {'Content-Type': 'text/plain'}), 404

    return application_menu(mailbox)


@blueprint.route('/messages/<mailbox>/menu')
def application_menu(mailbox):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox'), 403

    response = context.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'VoicemailBoxSummary',
        'Context': 'default',
        'Mailbox': mailbox,
        'Folder': 'INBOX'
    })
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    messages = []

    for element in document.findall('response/generic[@event="VoicemailBoxDetail"]'):
        message = element.get('id')
        messages.append(message)

    messages.sort()
    document = tag('CiscoIPPhoneMenu', tag('Title', 'Messages'))

    if len(messages):
        document.append(tag('MenuItem',
            tag('Name', 'New Messages (' + str(len(messages)) + ')'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/INBOX/' + messages[0])
        ))
    else:
        document.append(tag('MenuItem',
            tag('Name', 'Old Messages'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/Old')
        ))

    document.extend([
        tag('MenuItem',
            tag('Name', 'List Folders'),
            tag('URL', request.url_root + 'messages/' + mailbox)
        ),
        tag('MenuItem',
            tag('Name', 'Change Greetings'),
            tag('URL', request.url_root + 'greetings/' + mailbox)
        ),
        tag('MenuItem',
            tag('Name', 'Call Voicemail'),
            tag('URL', 'Dial:messages')
        )
    ])

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 3)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Exit'),
            tag('URL', 'Init:Messages'),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Select' if context.is_79xx else 'View'),
            tag('URL', 'SoftKey:Select'),
            tag('Position', '1' if context.is_79xx else next(position))
        )
    ])

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/messages/<mailbox>')
def list_folders(mailbox):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox'), 403

    response = context.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'VoicemailBoxSummary',
        'Context': 'default',
        'Mailbox': mailbox
    })
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    messages = {}

    for element in document.findall('response/generic[@event="VoicemailBoxDetail"]'):
        folder = element.get('folder', '')

        messages.setdefault(folder, 0)
        messages[folder] += 1

    document = tag('CiscoIPPhoneMenu', tag('Title', 'Folders'))

    for folder in FOLDER_NAMES:
        document.append(tag('MenuItem',
            tag('Name', ('New' if folder == 'INBOX' else folder) + (' (' + str(messages[folder]) + ')' if folder in messages else '')),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Select folder'))

    position = iter(map(str, range(1, 3)))

    # Stupid 88xx series needs Init:Messages instead of URL because it doesn't consider the application menu to be part of messages
    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/menu' if context.is_79xx else 'Init:Messages'),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Select' if context.is_79xx else 'View'),
            tag('URL', 'SoftKey:Select'),
            tag('Position', '1' if context.is_79xx else next(position))
        )
    ])

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/messages/<mailbox>/<folder>')
def list_messages(mailbox, folder):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox', headers = {'Content-Type': 'text/plain'}), 403

    if folder not in FOLDER_NAMES:
        return Response('Invalid folder', headers = {'Content-Type': 'text/plain'}), 403

    response = context.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'VoicemailBoxSummary',
        'Context': 'default',
        'Mailbox': mailbox,
        'Folder': folder
    })
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    messages = []

    for element in document.findall('response/generic[@event="VoicemailBoxDetail"]'):
        message = element.get('id')
        matches = re.search(r'(?x) ^ "(?P<name> [^"]*)" [ ]+ <(?P<extension> [^>]+)> $', element.get('callerid', ''))

        if matches:
            name, extension = matches.group('name'), matches.group('extension')
        else:
            name, extension = '', element.get('callerid', 'Anonymous')

        date = datetime.strptime(element.get('date', ''), '%a %b %d %I:%M:%S %p UTC %Y')
        date = date.replace(tzinfo = timezone.utc).astimezone().strftime('%H:%M, %d/%m/%Y')

        messages.append((message, name, extension, date))

    messages.sort(key = lambda message: message[0])
    pages = ceil(len(messages) / 20)

    try:
        page = int(request.args.get('page', '1'))

        if page < 1 or page > pages:
            raise ValueError

    except ValueError:
        page = 1

    document = tag('CiscoIPPhoneMenu',
        tag('Title', ('New' if folder == 'INBOX' else folder) + ' Messages' + (' ' + str(page) + '/' + str(pages) if pages > 1 else '')))

    for message, name, extension, date in messages[(page - 1) * 10:page * 10]:
        document.append(tag('MenuItem',
            tag('Name', (name + ', ' + extension if len(name) else extension) + '. ' + date),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Select message'))

    position = iter(map(str, range(1, 5)))

    document.append(tag('SoftKeyItem',
        tag('Name', 'Back' if context.is_79xx else 'Exit'),
        tag('URL', request.url_root + 'messages/' + mailbox),
        tag('Position', '3' if context.is_79xx else next(position))
    ))

    if len(messages):
        document.append(tag('SoftKeyItem',
            tag('Name', 'Details'),
            tag('URL', 'SoftKey:Select'),
            tag('Position', '1' if context.is_79xx else next(position))
        ))

    if page < pages:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Next'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '?page=' + str(page + 1)),
            tag('Position', '2' if context.is_79xx else next(position))
        ))

    if page > 1:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Previous'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '?page=' + str(page - 1)),
            tag('Position', '4' if context.is_79xx else next(position))
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/messages/<mailbox>/<folder>/<message>')
def read_message(mailbox, folder, message):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox', headers = {'Content-Type': 'text/plain'}), 403

    if folder not in FOLDER_NAMES:
        return Response('Invalid folder', headers = {'Content-Type': 'text/plain'}), 403

    if not re.search(r'(?x) ^ [0-9]+ - [0-9]+ $', message):
        return Response('Invalid message', headers = {'Content-Type': 'text/plain'}), 403

    response = context.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'VoicemailBoxSummary',
        'Context': 'default',
        'Mailbox': mailbox,
        'Folder': folder
    })
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    next_message = None
    previous_message = None
    exists = False

    for element in document.findall('response/generic[@event="VoicemailBoxDetail"]'):
        target_message = element.get('id')

        if target_message < message:
            previous_message = max(target_message, previous_message or target_message)

        elif target_message == message:
            exists = True
            matches = re.search(r'(?x) ^ "(?P<name> [^"]*)" [ ]+ <(?P<extension> [^>]+)> $', element.get('callerid', ''))

            if matches:
                name, extension = matches.group('name'), matches.group('extension')
            else:
                name, extension = '', element.get('callerid', 'Anonymous')

            date = datetime.strptime(element.get('date', ''), '%a %b %d %I:%M:%S %p UTC %Y')
            date = date.replace(tzinfo = timezone.utc).astimezone().strftime('%H:%M, %d/%m/%Y')

            duration = int(element.get('duration', 0))
            duration = '{0:02d}:{1:02d}'.format(duration // 60, duration % 60)

        elif target_message > message:
            next_message = min(target_message, next_message or target_message)

    if not exists:
        return list_messages(mailbox, folder)

    document = tag('CicoIPPhoneText',
        tag('Title', 'Message'),
        tag('Text', (name + ', ' if name else '') + extension + '.\nRecorded at ' + date + ' (' + duration + ').')
    )

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 9)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Play'),
            tag('URL', 'Dial:messages-' + message + '-' + extension),
            tag('Position', '1' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Delete'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message + '/delete'),
            tag('Position', '2' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Move'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message + '/move'),
            tag('Position', '4' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Forward'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message + '/forward'),
            tag('Position', '5' if context.is_79xx else next(position))
        )
    ])

    if extension != 'Anonymous':
        document.append(tag('SoftKeyItem',
            tag('Name', 'Dial' if context.is_79xx else 'Call'),
            tag('URL', 'Dial:' + extension),
            tag('Position', '6' if context.is_79xx else next(position))
        ))

    if next_message:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Next'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + next_message),
            tag('Position', '7' if context.is_79xx else next(position))
        ))

    if previous_message:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Previous'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + previous_message),
            tag('Position', '8' if context.is_79xx else next(position))
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/messages/<mailbox>/<folder>/<message>/delete')
def delete_message(mailbox, folder, message):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox', headers = {'Content-Type': 'text/plain'}), 403

    if folder not in FOLDER_NAMES:
        return Response('Invalid folder', headers = {'Content-Type': 'text/plain'}), 403

    if not re.search(r'(?x) ^ [0-9]+ - [0-9]+ $', message):
        return Response('Invalid message', headers = {'Content-Type': 'text/plain'}), 403

    response = context.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'VoicemailBoxSummary',
        'Context': 'default',
        'Mailbox': mailbox,
        'Folder': folder
    })
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    next_message = None
    previous_message = None
    exists = False

    for element in document.findall('response/generic[@event="VoicemailBoxDetail"]'):
        target_message = element.get('id')

        if target_message < message:
            previous_message = max(target_message, previous_message or target_message)

        elif target_message == message:
            exists = True
            matches = re.search(r'(?x) ^ "([^"]*)?" [ ]+ <(?P<extension> [^>]+)> $', element.get('callerid', ''))

            if matches:
                extension = matches.group('extension')
            else:
                extension = element.get('callerid', 'Anonymous')

        elif target_message > message:
            next_message = min(target_message, next_message or target_message)

    if not exists and folder != 'INBOX':
        return list_messages(mailbox, folder)

    # The message may have been automatically moved to Old when played so try deleting it from there
    response = context.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'VoicemailRemove',
        'Context': 'default',
        'Mailbox': mailbox,
        'Folder': 'Old' if not exists and folder == 'INBOX' else folder,
        'ID': message
    })
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    document = tag('CiscoIPPhoneText',
        tag('Title', 'Messages'),
        tag('Text', 'Message from ' + extension + ' deleted.'))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 4)))

    document.append(tag('SoftKeyItem',
        tag('Name', 'Back' if context.is_79xx else 'Exit')),
        tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder),
        tag('Position', '3' if context.is_79xx else next(position)
    ))

    if next_message:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Next'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + next_message),
            tag('Position', '1' if context.is_79xx else next(position))
        ))

    if previous_message:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Previous'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + previous_message),
            tag('Position', '2' if context.is_79xx else next(position))
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/messages/<mailbox>/<folder>/<message>/move')
@blueprint.route('/messages/<mailbox>/<folder>/<message>/move/<target_folder>')
def move_message(mailbox, folder, message, target_folder = None):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox'), 403

    if folder not in FOLDER_NAMES:
        return Response('Invalid folder'), 403

    if not re.search(r'(?x) ^ [0-9]+ - [0-9]+ $', message):
        return Response('Invalid message'), 403

    if target_folder is not None:
        if target_folder not in FOLDER_NAMES:
            return Response('Invalid target folder'), 403

        response = context.session.get(config.manager_url, timeout = 5, params = {
            'Action': 'VoicemailBoxSummary',
            'Context': 'default',
            'Mailbox': mailbox,
            'Folder': folder
        })
        response.raise_for_status()

        document = etree.fromstring(response.content)
        element = document.find('response/generic[@response="Error"]')

        if element is not None:
            error = element.get('message')

            raise Exception(error)

        next_message = None
        previous_message = None
        exists = False

        for element in document.findall('response/generic[@event="VoicemailBoxDetail"]'):
            target_message = element.get('id')

            if target_message < message:
                previous_message = max(target_message, previous_message or target_message)

            elif target_message == message:
                exists = True
                matches = re.search(r'(?x) ^ "([^"]*)?" [ ]+ <(?P<extension> [^>]+)> $', element.get('callerid', ''))

                if matches:
                    extension = matches.group('extension')
                else:
                    extension = element.get('callerid', 'Anonymous')

            elif target_message > message:
                next_message = min(target_message, next_message or target_message)

        if not exists and folder != 'INBOX':
            return list_messages(mailbox, folder)

        response = context.session.get(config.manager_url, timeout = 5, params = {
            'Action': 'VoicemailMove',
            'Context': 'default',
            'Mailbox': mailbox,
            'Folder': 'Old' if not exists and folder == 'INBOX' else folder,
            'ID': message,
            'ToFolder': target_folder
        })
        response.raise_for_status()

        document = etree.fromstring(response.content)
        element = document.find('response/generic[@response="Error"]')

        if element is not None:
            error = element.get('message')

            raise Exception(error)

        document = tag('CiscoIPPhoneText',
            tag('Title', 'Messages'),
            tag('Text', 'Message from ' + extension + ' moved to ' + ('New' if target_folder == 'INBOX' else target_folder) + ' folder.'))

        if context.is_79xx:
            document.append(tag('Prompt', 'Your current options'))

        position = iter(map(str, range(1, 4)))

        document.append(tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder),
            tag('Position', '3' if context.is_79xx else next(position))
        ))

        if next_message:
            document.append(tag('SoftKeyItem',
                tag('Name', 'Next'),
                tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + next_message),
                tag('Position', '1' if context.is_79xx else next(position))
            ))

        if previous_message:
            document.append(tag('SoftKeyItem',
                tag('Name', 'Previous'),
                tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + previous_message),
                tag('Position', '2' if context.is_79xx else next(position))
            ))

        xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

        return Response(xml, headers = {
            'Content-Type': 'text/xml',
            'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
        }), 200

    document = tag('CiscoIPPhoneMenu', tag('Title', 'Move Message To'))

    for target_folder in FOLDER_NAMES:
        if folder == target_folder:
            continue

        document.append(tag('MenuItem',
            tag('Name', 'New' if target_folder == 'INBOX' else target_folder),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message + '/move/' + target_folder)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Select folder'))

    position = iter(map(str, range(1, 3)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Select' if context.is_79xx else 'Move'),
            tag('URL', 'SoftKey:Select'),
            tag('Position', '1' if context.is_79xx else next(position))
        )
    ])

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/messages/<mailbox>/<folder>/<message>/forward')
@blueprint.route('/messages/<mailbox>/<folder>/<message>/forward/<target_mailbox>')
def forward_message(mailbox, folder, message, target_mailbox = None):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox', headers = {'Content-Type': 'text/plain'}), 403

    if folder not in FOLDER_NAMES:
        return Response('Invalid folder', headers = {'Content-Type': 'text/plain'}), 403

    if not re.search(r'(?x) ^ [0-9]+ - [0-9]+ $', message):
        return Response('Invalid message', headers = {'Content-Type': 'text/plain'}), 403

    if target_mailbox is not None:
        if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', target_mailbox):
            return Response('Invalid target mailbox'), 403

        response = context.session.get(config.manager_url, timeout = 5, params = {
            'Action': 'VoicemailBoxSummary',
            'Context': 'default',
            'Mailbox': mailbox,
            'Folder': folder
        })
        response.raise_for_status()

        document = etree.fromstring(response.content)
        element = document.find('response/generic[@response="Error"]')

        if element is not None:
            error = element.get('message')

            raise Exception(error)

        next_message = None
        previous_message = None
        exists = False

        for element in document.findall('response/generic[@event="VoicemailBoxDetail"]'):
            target_message = element.get('id')

            if target_message < message:
                previous_message = max(target_message, previous_message or target_message)

            elif target_message == message:
                exists = True
                matches = re.search(r'(?x) ^ "([^"]*)?" [ ]+ <(?P<extension> [^>]+)> $', element.get('callerid', ''))

                if matches:
                    extension = matches.group('extension')
                else:
                    extension = element.get('callerid', 'Anonymous')

            elif target_message > message:
                next_message = min(target_message, next_message or target_message)

        if not exists and folder != 'INBOX':
            return list_messages(mailbox, folder)

        response = context.session.get(config.manager_url, timeout = 5, params = {
            'Action': 'VoicemailForward',
            'Context': 'default',
            'Mailbox': mailbox,
            'Folder': 'Old' if not exists and folder == 'INBOX' else folder,
            'ID': message,
            'ToContext': 'default',
            'ToMailbox': target_mailbox,
            'ToFolder': 'INBOX'
        })
        response.raise_for_status()

        document = etree.fromstring(response.content)
        element = document.find('response/generic[@response="Error"]')

        if element is not None:
            error = element.get('message')

            raise Exception(error)

        document = tag('CiscoIPPhoneText',
            tag('Title', 'Messages'),
            tag('Text', 'Message from ' + extension + ' forwarded to mailbox ' + target_mailbox + '.'))

        if context.is_79xx:
            document.append(tag('Prompt', 'Your current options'))

        position = iter(map(str, range(1, 4)))

        document.append(tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder),
            tag('Position', '3' if context.is_79xx else next(position))
        ))

        if next_message:
            document.append(tag('SoftKeyItem',
                tag('Name', 'Next'),
                tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + next_message),
                tag('Position', '1' if context.is_79xx else next(position))
            ))

        if previous_message:
            document.append(tag('SoftKeyItem',
                tag('Name', 'Previous'),
                tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + previous_message),
                tag('Position', '2' if context.is_79xx else next(position))
            ))

        xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

        return Response(xml, headers = {
            'Content-Type': 'text/xml',
            'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
        }), 200

    response = context.session.get(config.manager_url, timeout = 5, params = {'Action': 'VoicemailUsersList'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    mailboxes = []

    for element in document.findall('response/generic[@event="VoicemailUserEntry"]'):
        target_mailbox = element.get('voicemailbox')

        if target_mailbox == mailbox:
            continue

        name = element.get('fullname', '')
        mailboxes.append((target_mailbox, name))

    mailboxes.sort(key = lambda mailbox: mailbox[0])
    pages = ceil(len(mailboxes) / 10)

    try:
        page = int(request.args.get('page', '1'))

        if page < 1 or page > pages:
            raise ValueError

    except ValueError:
        page = 1

    document = tag('CiscoIPPhoneMenu',
        tag('Title', 'Forward Message To' + (' ' + str(page) + '/' + str(pages) if pages > 1 else '')))

    for target_mailbox, name in mailboxes[(page - 1) * 10:page * 10]:
        document.append(tag('MenuItem',
            tag('Name', target_mailbox + (', ' + name if name else '')),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message + '/forward/' + target_mailbox)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Select mailbox'))

    position = iter(map(str, range(1, 5)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Select' if context.is_79xx else 'Forward'),
            tag('URL', 'SoftKey:Select'),
            tag('Position', '1' if context.is_79xx else next(position))
        )
    ])

    if page < pages:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Next'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message + '/forward?page=' + str(page + 1)),
            tag('Position', '2' if context.is_79xx else next(position))
        ))

    if page > 1:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Previous'),
            tag('URL', request.url_root + 'messages/' + mailbox + '/' + folder + '/' + message + '/forward?page=' + str(page - 1)),
            tag('Position', '4' if context.is_79xx else next(position))
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/greetings/<mailbox>')
def list_greetings(mailbox):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox', headers = {'Content-Type': 'text/plain'}), 403

    document = tag('CiscoIPPhoneMenu', tag('Title', 'Greetings'))

    for greeting in GREETING_NAMES:
        document.append(tag('MenuItem',
            tag('Name', greeting),
            tag('URL', request.url_root + 'greetings/' + mailbox + '/' + greeting)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Select greeting'))

    position = iter(map(str, range(1, 3)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', 'SoftKey:Exit' if context.is_79xx else 'Init:Messages'),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Change'),
            tag('URL', 'SoftKey:Select'),
            tag('Position', '1' if context.is_79xx else next(position))
        )
    ])

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/greetings/<mailbox>/<greeting>')
def change_greeting(mailbox, greeting):
    if not re.search(r'(?x) ^ [a-zA-Z0-9_-]+ $', mailbox):
        return Response('Invalid mailbox', headers = {'Content-Type': 'text/plain'}), 403

    if not greeting in GREETING_NAMES:
        return Response('Invalid greeting', headers = {'Content-Type': 'text/plain'}), 403

    document = tag('CiscoIPPhoneText',
        tag('Title', greeting + ' Greeting'),
        tag('Text', 'Press Play to hear the current greeting.\nPress Record to change the greeting.'))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 4)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'greetings/' + mailbox),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Play'),
            tag('URL', 'Dial:greeting-' + greeting.lower()),
            tag('Position', '1' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Record'),
            tag('URL', 'Dial:recgreeting-' + greeting.lower()),
            tag('Position', '2' if context.is_79xx else next(position))
        )
    ])

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
