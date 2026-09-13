#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import re
from math import ceil
import traceback

import requests
from lxml import etree
from lxml.builder import E as tag
from flask import Blueprint, Response, request, g as context

import config


blueprint = Blueprint('services', __name__)


@blueprint.route('/services')
def application_menu():
    if context.is_79xx:
        return list_services()

    document = tag('CiscoIPPhoneMenu',
        tag('MenuItem',
            tag('Name', 'External Services'),
            tag('URL', request.url_root + 'services/menu')
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/services/menu')
def list_services():
    document = tag('CiscoIPPhoneMenu',
        tag('Title', 'Services'),
        tag('MenuItem',
            tag('Name', 'Parked Calls'),
            tag('URL', request.url_root + 'services/parked-calls')
        ))

    if len(config.busy_extensions):
        document.append(tag('MenuItem',
            tag('Name', 'Busy Extensions'),
            tag('URL', request.url_root + 'services/busy-extensions')
        ))

    if len(config.night_mode):
        document.append(tag('MenuItem',
            tag('Name', 'Night Mode'),
            tag('URL', request.url_root + 'services/night-mode')
        ))

    if len(config.weather_report_latitude) and len(config.weather_report_longitude):
        document.append(tag('MenuItem',
            tag('Name', 'Weather Report'),
            tag('URL', request.url_root + 'services/weather-report')
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 3)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Exit'),
            tag('URL', 'Init:Services'),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Select' if context.is_79xx else 'View'),
            tag('URL', 'Init:Services'),
            tag('Position', '1' if context.is_79xx else next(position))
        )
    ])

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/services/parked-calls')
def parked_calls():
    response = context.session.get(config.manager_url, timeout = 5, params = {'Action': 'ParkedCalls'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    calls = []

    for element in document.findall('response/generic[@event="ParkedCall"]'):
        extension = element.get('parkingspace')
        name = element.get('parkeecalleridname', element.get('parkeecalleridnum', 'Anonymous'))

        calls.append((extension, name))

    calls.sort(key = lambda call: call[0])

    document = tag('CiscoIPPhoneDirectory', tag('Title', 'Parked Calls'))

    for extension, name in calls:
        document.append(tag('DirectoryEntry',
            tag('Name', name),
            tag('Telephone', extension)
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 4)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'services/menu'),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Dial' if context.is_79xx else 'Call'),
            tag('URL', 'SoftKey:Select'),
            tag('Position', '1' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Refresh'),
            tag('URL', 'SoftKey:Update'),
            tag('Position', '2' if context.is_79xx else next(position))
        )
    ])

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/services/busy-extensions')
def busy_extensions():
    if not len(config.busy_extensions):
        return Response('No busy extensions', headers = {'Content-Type': 'text/plain'}), 404

    extensions = set(re.split('(?x) [ ,]+', config.busy_extensions))

    response = context.session.get(config.manager_url, timeout = 5, params = {'Action': 'SIPPeers'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    element = document.find('response/generic[@response="Error"]')

    if element is not None:
        error = element.get('message')

        raise Exception(error)

    extensions = []

    for element in document.findall('response/generic[@event="SIPPeer"]'):
        extension = element.get('name')

        if extension not in extensions:
            continue

        max_calls = int(element.get('maxcalls'))
        off_hook = int(element.get('offhook'))
        ringing = int(element.get('ringing'))
        in_use = int(element.get('inuse'))
        do_not_disturb = element.get('donotdisturb') == 'yes'
        call_forward = element.get('callforward')

        if not (off_hook or ringing or in_use or do_not_disturb or len(call_forward)):
            continue

        extensions.append((extension, max_calls, off_hook, ringing, in_use, do_not_disturb, call_forward))

    extensions.sort(key = lambda extension: extension[0])
    pages = ceil(len(extensions) / 10)

    try:
        page = int(request.args.get('page', '1'))

        if page < 1 or page > pages:
            raise ValueError

    except ValueError:
        page = 1

    document = tag('CiscoIPPhoneMenu', tag('Title', 'Busy Extensions'))

    for extension, max_calls, off_hook, ringing, in_use, do_not_disturb, call_forward in extensions[(page - 1) * 10:page * 10]:
        status = []

        if ringing + in_use == max_calls:
            status.append('Busy')
        elif ringing:
            status.append('Ringing')
        elif in_use or off_hook:
            status.append('On the Phone')

        if do_not_disturb:
            status.append('Do Not Disturb')

        if len(call_forward):
            status.append('Forwarded to ' + call_forward)

        document.append(tag('MenuItem',
            tag('Name', extension + ': ' + ', '.join(status)),
            tag('URL', 'SoftKey:Update')
        ))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 5)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'services/menu'),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Refresh'),
            tag('URL', 'SoftKey:Update'),
            tag('Position', '1' if context.is_79xx else next(position))
        )
    ])

    if page < pages:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Next'),
            tag('URL', request.url_root + 'busy-extensions?page=' + str(page + 1)),
            tag('Position', '2' if context.is_79xx else next(position))
        ))

    if page > 1:
        document.append(tag('SoftKeyItem',
            tag('Name', 'Previous'),
            tag('URL', request.url_root + 'busy-extensions?page=' + str(page - 1)),
            tag('Position', '4' if context.is_79xx else next(position))
        ))

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/services/night-mode')
@blueprint.route('/services/night-mode/<enabled>')
def night_mode(enabled = None):
    if not len(config.night_mode):
        return Response('No night mode', headers = {'Content-Type': 'text/plain'}), 404

    if enabled is not None:
        if enabled not in ('yes', 'no'):
            return Response('Invalid enabled', headers = {'Content-Type': 'text/plain'}), 500

        response = context.session.get(config.manager_url, timeout = 5, params = {
            'Action': 'SetVar',
            'Variable': 'DB(' + config.night_mode + ')',
            'Value': enabled
        })
        response.raise_for_status()

        document = etree.fromstring(response.content)
        element = document.find('response/generic[@response="Error"]')

        if element is not None:
            error = element.get('message')

            raise Exception(error)

    else:
        response = context.session.get(config.manager_url, timeout = 5, params = {
            'Action': 'GetVar',
            'Variable': 'DB(' + config.night_mode + ')'
        })
        response.raise_for_status()

        document = etree.fromstring(response.content)
        element = document.find('response/generic[@response="Error"]')

        if element is not None:
            error = element.get('message')

            raise Exception(error)

        element = document.find('response/generic[@response="Success"]')

        if element is not None:
            enabled = element.get('value')
        else:
            enabled = 'no'

    document = tag('CiscoIPPhoneText',
        tag('Title', 'Night Mode'),
        tag('Text', 'Night mode is ' + ('enabled' if enabled == 'yes' else 'disabled')))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 3)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'services/menu'),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Enable' if enabled == 'no' else 'Disable'),
            tag('URL', request.url_root + 'services/night-mode/' + ('no' if enabled == 'yes' else 'yes')),
            tag('Position', '1' if context.is_79xx else next(position))
        )
    ])

    xml = etree.tostring(document, xml_declaration = True, encoding = 'UTF-8', pretty_print = True).decode()

    return Response(xml, headers = {
        'Content-Type': 'text/xml',
        'Expires': 'Thu, 01 Jan 1970 00:00:00 GMT'
    }), 200


@blueprint.route('/services/weather-report')
def weather_report():
    if not len(config.weather_report_latitude) or not len(config.weather_report_longitude):
        return Response('No weather report', headers = {'Content-Type': 'text/plain'}), 404

    try:
        response = requests.get('https://api.open-meteo.com/v1/forecast', timeout = 10, params = {
            'latitude': config.weather_report_latitude,
            'longitude': config.weather_report_longitude,
            'timezone': 'GMT',
            'current': 'temperature_2m,apparent_temperature,precipitation,precipitation_probability,wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure',
            'daily': 'temperature_2m_max,temperature_2m_min',
            'temperature_unit': 'fahrenheit' if config.weather_report_units != 'metric' else 'celsius',
            'wind_speed_unit': 'mph' if config.weather_report_units != 'metric' else 'kmh',
            'precipitation_unit': 'inch' if config.weather_report_units != 'metric' else 'mm'
        })
    except Exception as error:
        return Response(error)

    if response.status_code != 200:
        return Response(response.status_line, headers = {'Content-Type': 'text/plain'}), 500

    forecast = response.json()

    report = 'Temperature is {0}{1}'.format(
        forecast['current']['temperature_2m'],
        forecast['current_units']['temperature_2m'][1:]
    )

    if forecast['current']['apparent_temperature'] != forecast['current']['temperature_2m']:
        report += ' (feels like {0}{1})'.format(
            forecast['current']['apparent_temperature'],
            forecast['current_units']['apparent_temperature'][1:]
        )

    report += ' with a low of {0}{1} and a high of {2}{3}.\n\nRainfall is {4}{5}'.format(
        forecast['daily']['temperature_2m_min'][0],
        forecast['daily_units']['temperature_2m_min'][1:],
        forecast['daily']['temperature_2m_max'][0],
        forecast['daily_units']['temperature_2m_max'][1:],
        forecast['current']['precipitation'],
        forecast['current_units']['precipitation'],
    )

    if forecast['current']['precipitation_probability']:
        report = ' with a {0}{1} chance of rain'.format(
           forecast['current']['precipitation_probability'],
           forecast['current_units']['precipitation_probability']
       )

    report += ' and a pressure of {0}{1}.\n\nWind is {2}{3} from the {4} with gusts of up to {5}{6}.'.format(
        forecast['current']['surface_pressure'],
        forecast['current_units']['surface_pressure'],
        forecast['current']['wind_speed_10m'],
        forecast['current_units']['wind_speed_10m'],
        ['north', 'northeast', 'east', 'southeast',
         'south', 'southwest', 'west', 'northwest'][int((forecast['current']['wind_direction_10m'] + 22.5) / 45) % 8],
        forecast['current']['wind_gusts_10m'],
        forecast['current_units']['wind_gusts_10m']
    )

    document = tag('CiscoIPPhoneText',
        tag('Title', 'Weather Report'),
        tag('Text', report))

    if context.is_79xx:
        document.append(tag('Prompt', 'Your current options'))

    position = iter(map(str, range(1, 3)))

    document.extend([
        tag('SoftKeyItem',
            tag('Name', 'Back' if context.is_79xx else 'Exit'),
            tag('URL', request.url_root + 'services/menu'),
            tag('Position', '3' if context.is_79xx else next(position))
        ),
        tag('SoftKeyItem',
            tag('Name', 'Refresh'),
            tag('URL', 'SoftKey:Update'),
            tag('Position', '1' if context.is_79xx else next(position))
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
