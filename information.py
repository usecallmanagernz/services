#!/usr/bin/env python3
#
# Copyright (c) 2024 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import re
import traceback
from html import escape

from lxml import etree
from flask import Blueprint, Response, request


blueprint = Blueprint('information', __name__)


@blueprint.route('/information')
def help_information():
    id = request.args.get('id', '')

    if not re.search(r'(?x) ^ [0-9]+ $', id):
        return Response('Invalid id', mimetype = 'text/plain'), 500

    document = etree.parse('./phone_help.xml')
    element = document.find(f'HelpItem[ID="{id}"]')

    if element:
        title = element.find('Title').text
        text = element.find('Text').text
    else:
        title = 'Information'
        text = 'Sorry, no help on that topic.'

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneText>\n'
           '  <Title>' + escape(title) + '</Title>\n'
           '  <Text>' + escape(text) + '</Text>\n'
           '  <Prompt>Your current options</Prompt>\n'
           '  <SoftKeyItem>\n'
           '    <Name>Exit</Name>\n'
           '    <Position>3</Position>\n'
           '    <URL>Key:Info</URL>\n'
           '  </SoftKeyItem>\n'
           '</CiscoIPPhoneText>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.errorhandler(Exception)
def error_handler(error):
    traceback.print_exc(file = sys.stderr)

    return Response(str(error), mimetype = 'text/plain'), 500
