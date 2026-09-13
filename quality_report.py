#!/usr/bin/env python3
#
# Copyright (c) 2025 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import re
import traceback
from datetime import datetime
import json

import requests
from lxml import etree
from lxml.builder import E as tag
from flask import Blueprint, Response, request, g as context

import config


blueprint = Blueprint('quality_report', __name__)


REPORT_REASONS = [
    'I could not hear them',
    'They could not hear me',
    'Audio had echo',
    'Audio had crackling',
    'Audio sounded underwater',
    'Other issue (unspecified)',
]


@blueprint.route('/quality-report')
def get_reason():
    device_name = request.args.get('name', '')

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name):
        return Response('Invalid device', headers = {'Content-Type': 'text/plain'}), 403

    document = tag('CiscoIPPhoneMenu', tag('Title', 'Quality Report'))

    for reason in range(0, len(REPORT_REASONS)):
        document.append(tag('MenuItem',
            tag('Name', REPORT_REASONS[reason]),
            tag('URL', request.url_root + 'quality-report/' + str(reason) + '?name=' + device_name)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Select reason'))

    document.append(tag('SoftKeyItem',
        tag('Name', 'Exit'),
        tag('URL', 'SoftKey:Exit'),
        tag('Position', '3' if context.is_79xx else '1')
    ))

    document.append(tag('SoftKeyItem',
        tag('Name', 'Send'),
        tag('URL', 'SoftKey:Select'),
        tag('Position', '1' if context.is_79xx else '2')
    ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/quality-report/<reason>')
def save_report(reason):
    device_name = request.args.get('name', '')

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name):
        return Response('Invalid device', headers = {'Content-Type': 'text/plain'}), 403

    try:
        reason = int(reason)

        if reason < 0 or reason > len(REPORT_REASONS) - 1:
            raise ValueError

    except ValueError:
        return Response('Invalid reason', headers = {'Content-Type': 'text/plain'}), 403

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
        return Response('Device not found', headers = {'Content-Type': 'text/plain'}), 404

    ip_address = element.get('ipaddress')
    status = element.get('status')

    audio_rtp_rx = element.get('audiortprxstat')
    audio_rtp_tx = element.get('audiortptxstat')

    video_rtp_rx = element.get('videortprxstat')
    video_rtp_tx = element.get('videortptxstat')

    with open(f'{config.reports_dir}/qrt-{device_name}.json', 'a', encoding='utf-8') as file:
        file.write(json.dumps({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip_address': ip_address,
            'status': status,
            'reason': REPORT_REASONS[reason],
            'audio_rtp': {'rx': audio_rtp_rx, 'tx': audio_rtp_tx},
            'video_rtp': {'rx': video_rtp_rx, 'tx': video_rtp_tx}
        }) + "\n")

    document = tag('CiscoIPPhoneText',
        tag('Title', 'Quality Report'),
        tag('Text', REPORT_REASONS[reason] + ' has been reported.'))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options</Prompt>'))

    document.append(tag('SoftKeyItem',
        tag('Name', 'Exit'),
        tag('URL', 'SoftKey:Exit'),
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
