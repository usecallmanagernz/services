#!/usr/bin/python3

import os.path
import re
from urllib.parse import quote_plus
from html import escape
from lxml import etree
import requests
from flask import Blueprint, Response, request, g
import config


blueprint = Blueprint('services', __name__)


@blueprint.route('/services')
def services_menu():
    content = '<?xml version="1.0" encoding="UTF-8"?>' \
        '<CiscoIPPhoneMenu>' \
          '<Title>Services</Title>' \
          '<MenuItem>' \
            '<Name>Parked Calls</Name>' \
            '<URL>' + request.url_root + 'services/parked-calls?name=' + quote_plus(g.device_name) + '</URL>' \
          '</MenuItem>'

    if g.is_79xx:
        content += '<Prompt>Your current options</Prompt>'

    content += '<SoftKeyItem>' \
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

    return Response(content, mimetype = 'text/xml'), 200


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

    response = session.get(config.manager_url, timeout = 5, params = {'Action': 'Logoff'})
    response.raise_for_status()

    content = '<?xml version="1.0" encoding="UTF-8"?>' \
        '<CiscoIPPhoneMenu>' \
          '<Title>Parked Calls</Title>'

    for extension, name in calls:
        content += '<MenuItem>' \
                     '<Name>' + escape(name) + '</Name>' \
                     '<URL>Dial:' + quote_plus(extension) + '</URL>' \
                   '</MenuItem>'

    if g.is_79xx:
        content += '<Prompt>Select call</Prompt>'

    content += '<SoftKeyItem>' \
            '<Name>Exit</Name>' \
            '<Position>' + ('3' if g.is_79xx else '1') + '</Position>' \
            '<URL>' + request.url_root + 'services?name=' + quote_plus(g.device_name) + '</URL>' \
          '</SoftKeyItem>' \
          '<SoftKeyItem>' \
            '<Name>Dial</Name>' \
            '<Position>' + ('1' if g.is_79xx else '2') + '</Position>' \
            '<URL>SoftKey:Select</URL>' \
          '</SoftKeyItem>' \
          '<SoftKeyItem>' \
            '<Name>Update</Name>' \
            '<Position>' + ('2' if g.is_79xx else '3') + '</Position>' \
            '<URL>SoftKey:Update</URL>' \
          '</SoftKeyItem>' \
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
