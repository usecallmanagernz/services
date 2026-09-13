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
from lxml.builder import E as tag
from flask import Blueprint, Response, request


blueprint = Blueprint('information', __name__)


@blueprint.route('/information')
def help_information():
    id = request.args.get('id', '')

    if not re.search(r'(?x) ^ [0-9]+ $', id):
        return Response('Invalid id', headers = {'Content-Type': 'text/plain'}), 500

    document = etree.parse('./phone_help.xml')
    element = document.find('HelpItem[ID="' + escape(id) + '"]')

    if element is not None:
        title = element.find('Title').text
        text = element.find('Text').text
    else:
        title = 'Information'
        text = 'Sorry, no help on that topic.'

    document = tag('CiscoIPPhoneText',
        tag('Title', title),
        tag('Text', text),
        tag('Prompt', 'Your current options'),
        tag('SoftKey',
            tag('Name', 'Exit'),
            tag('URL', 'Key:Info'),
            tag('Position', '3')
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.errorhandler(Exception)
def error_handler(error):
    traceback.print_exc(file = sys.stderr)

    return Response(str(error), headers = {'Content-Type': 'text/plain'}), 500
