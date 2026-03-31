#!/usr/bin/env python3
#
# Copyright (c) 2025 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import re
import traceback
from urllib.parse import quote_plus
from html import escape
from datetime import datetime
import json

import requests
from lxml import etree
from flask import Blueprint, Response, request, g

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
        return Response('Invalid device', mimetype = 'text/plain'), 403

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneMenu>\n'
           '  <Title>Quality Report</Title>\n')

    for reason in range(0, len(REPORT_REASONS)):
        xml += ('  <MenuItem>\n'
                '    <Name>' + escape(REPORT_REASONS[reason]) + '</Name>\n'
                '    <URL>' + request.url_root + f'quality-report/{reason}' + '?name=' + quote_plus(device_name) + '</URL>\n'
                '  </MenuItem>\n')

    if g.is_79xx:
        xml += '  <Prompt>Select reason</Prompt>'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Submit</Name>\n'
            '    <URL>SoftKey:Select</URL>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <URL>Init:Services</URL>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneMenu>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/quality-report/<reason>')
def send_report(reason):
    device_name = request.args.get('name', '')

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name):
        return Response('Invalid device', mimetype = 'text/plain'), 403

    try:
        reason = int(reason)

        if reason < 0 or reason > len(REPORT_REASONS) - 1:
            raise ValueError

    except ValueError:
        return Response('Invalid reason', mimetype = 'text/plain'), 403

    response = g.session.get(config.manager_url, timeout = 5, params = {
        'Action': 'SIPShowPeer',
        'DeviceName': device_name
    })
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Success"]')

    if element is None:
        return Response('Device not found', mimetype = 'text/plain'), 404

    ip_address = element.get('ipaddress')
    status = element.get('status')

    rtp_rx_stat = element.get('rtprxstat')
    rtp_tx_stat = element.get('rtptxstat')

    with open(f'{config.reports_dir}/qrt-{device_name}.json', 'a', encoding='utf-8') as file:
        file.write(json.dumps({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip_address': ip_address,
            'status': status,
            'reason': REPORT_REASONS[reason],
            'rtp_rx_stat': rtp_rx_stat,
            'rtp_tx_stat': rtp_tx_stat,
        }) + "\n")

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneText>\n'
           '  <Title>Quality Report</Title>\n'
           '  <Text>' + escape(REPORT_REASONS[reason]) + ' has been reported.</Text>\n')

    if g.is_79xx:
        xml += '  <Prompt>Your current options</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <URL>Init:Services</URL>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneText>\n')

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
