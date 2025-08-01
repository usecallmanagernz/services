#!/usr/bin/env python3
#
# Copyright (c) 2025 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import re
from urllib.parse import quote_plus
from html import escape
from datetime import datetime
import json

import requests
from lxml import etree
from flask import Blueprint, Response, request, g
import config


blueprint = Blueprint('quality_report', __name__)


REPORT_REASONS = {
    '0': 'Audio had echo',
    '1': 'Audio had crackling',
    '2': 'I could not hear them',
    '3': 'They could not hear me',
    '4': 'Other issue (unspecified)',
}


@blueprint.route('/quality-report')
def quality_report():
    device_name = request.args.get('name', '')

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name):
        return Response('Invalid device', mimetype = 'text/plain'), 403

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneMenu>\n'
           '  <Title>Quality Report</Title>\n')

    for reason in REPORT_REASONS.keys():
        xml += ('  <MenuItem>\n'
                '    <Name>' + escape(REPORT_REASONS.get(reason, '')) + '</Name>\n'
                '    <URL>QueryStringParam:reason=' + quote_plus(reason) + '</URL>\n'
                '  </MenuItem>\n')

    if g.is_79xx:
        xml += '  <Prompt>Select reason</Prompt>'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Submit</Name>\n'
            '    <URL>' + request.url_root + 'quality-report/send?name=' + quote_plus(device_name) + '</URL>\n' + 
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <URL>Init:Services</URL>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneMenu>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/quality-report/send')
def quality_report_send():
    device_name = request.args.get('name', '')

    if not re.search(r'(?x) ^ SEP [0-9A-F]{12} $', device_name):
        return Response('Invalid device', mimetype = 'text/plain'), 403

    session = requests.Session()

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'Login',
                                                                      'Username': config.manager_username,
                                                                      'Secret': config.manager_secret})
    response.raise_for_status()

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'SIPPeers'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@event="SIPPeer"]/[@devicename="' + device_name + '"]')

    ip_address = None
    status = None

    rtp_rx_stat = None
    rtp_tx_stat = None

    if element is not None:
        peer_name = element.get('name')

        response = session.get(config.manager_url, timeout = 5, params = {'Action': 'SIPShowPeer',
                                                                          'Peer': peer_name})
        response.raise_for_status()

        document = etree.fromstring(response.content)
        element = document.find('response/generic[@name]')

        if element is not None:
            ip_address = element.get('ipaddress')
            status = element.get('status')

            rtp_rx_stat = element.get('rtprxstat')
            rtp_tx_stat = element.get('rtptxstat')

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'Logoff'})
    response.raise_for_status()

    reason = request.args.get('reason', '')

    with open(f'{config.reports_dir}/qrt-{device_name}.json', 'a', encoding='utf-8') as file:
        file.write(json.dumps({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip_address': ip_address,
            'status': status,
            'reason': REPORT_REASONS.get(reason, ''),
            'rtp_rx_stat': rtp_rx_stat,
            'rtp_tx_stat': rtp_tx_stat,
        }) + "\n")

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneText>\n'
           '  <Title>Quality Report</Title>\n'
           '  <Text>' + escape(REPORT_REASONS.get(reason, '')) + ' has been reported.</Text>\n')

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
    g.is_79xx = re.search(r'(?x) ^ CP-79', request.headers.get('X-CiscoIPPhoneModelName', ''))


@blueprint.errorhandler(Exception)
def error_handler(error):
    return Response(str(error), mimetype = 'text/plain'), 500
