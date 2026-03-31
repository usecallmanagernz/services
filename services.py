#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import sys
import re
import traceback
from urllib.parse import quote_plus
from html import escape

import requests
from lxml import etree
from flask import Blueprint, Response, request, g

import config


blueprint = Blueprint('services', __name__)


@blueprint.route('/services')
def services_menu():
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneMenu>\n'
           '  <Title>Services</Title>\n'
           '  <MenuItem>\n'
           '    <Name>Parked Calls</Name>\n'
           '    <URL>' + request.url_root + 'services/parked-calls</URL>\n'
           '  </MenuItem>\n')

    if len(config.night_mode):
        xml += ('  <MenuItem>\n'
                '    <Name>Night Mode</Name>\n'
                '    <URL>' + request.url_root + 'services/night-mode</URL>\n'
                '  </MenuItem>\n')

    if len(config.weather_report_latitude) and len(config.weather_report_longitude):
        xml += ('  <MenuItem>\n'
                '    <Name>Weather Report</Name>\n'
                '    <URL>' + request.url_root + 'services/weather-report</URL>\n'
                '  </MenuItem>\n')

    if g.is_79xx:
        xml += '  <Prompt>Your current options</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '    <URL>Init:Services</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Select</Name>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '    <URL>SoftKey:Select</URL>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneMenu>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/services/parked-calls')
def parked_calls():
    response = g.session.get(config.manager_url, timeout = 5, params = {'Action': 'ParkedCalls'})
    response.raise_for_status()

    document = etree.fromstring(response.content)
    calls = []

    for element in document.findall('response/generic[@event="ParkedCall"]'):
        extension = element.get('parkingspace')
        name = element.get('parkeecalleridname', element.get('parkeecalleridnum', 'Anonymous'))

        calls.append((extension, name))

    calls.sort(key = lambda call: call[0])

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneDirectory>\n'
           '  <Title>Parked Calls</Title>\n')

    for extension, name in calls:
        xml += ('<DirectoryEntry>\n'
                '  <Name>' + escape(name) + '</Name>\n'
                '  <Telephone>' + quote_plus(extension) + '</Telephone>\n'
                '</DirectoryEntry>\n')

    if g.is_79xx:
        xml += '  <Prompt>Select call</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '    <URL>' + request.url_root + 'services</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>' + ('Dial' if g.is_79xx else 'Call') + '</Name>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '    <URL>SoftKey:Select</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Update</Name>\n'
            '    <Position>' + ('2' if g.is_79xx else '3') + '</Position>\n'
            '    <URL>SoftKey:Update</URL>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneDirectory>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/services/night-mode')
@blueprint.route('/services/night-mode/<enabled>')
def night_mode(enabled = None):
    if not len(config.night_mode):
        return Response('No night mode', mimetype = 'text/plain'), 404

    if enabled is not None:
        if enabled not in ('yes', 'no'):
            return Response('Invalid enabled', mimetype = 'text/plain'), 500

        response = g.session.get(config.manager_url, timeout = 5, params = {
            'Action': 'SetVar',
            'Variable': f'DB({config.night_mode})',
            'Value': enabled
        })
        response.raise_for_status()
    else:
        response = g.session.get(config.manager_url, timeout = 5, params = {
            'Action': 'GetVar',
            'Variable': f'DB({config.night_mode})'
        })
        response.raise_for_status()

        document = etree.fromstring(response.content)
        element = document.find('response/generic[@response="Success"]')

        enabled = element.get('value') if element is not None else 'no'

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneText>\n'
           '  <Title>Night Mode</Title>\n'
           '  <Text>Night mode is ' + ('enabled' if enabled == 'yes' else 'disabled') + '.</Text>\n')

    if g.is_79xx:
        xml += '  <Prompt>Your current options</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '    <URL>' + request.url_root + 'services</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Change</Name>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '    <URL>' + request.url_root + 'services/night-mode/' + ('no' if enabled == 'yes' else 'yes') + '</URL>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneText>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/services/weather-report')
def weather_report():
    if not len(config.weather_report_latitude) or not len(config.weather_report_longitude):
        return Response('No weather report', mimetype = 'text/plain'), 404

    response = requests.get(f'https://api.open-meteo.com/v1/forecast', timeout = 10, params = {
        'latitude': config.weather_report_latitude,
        'longitude': config.weather_report_longitude,
        'timezone': 'GMT',
        'current': 'temperature_2m,apparent_temperature,precipitation,precipitation_probability,wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure',
        'daily': 'temperature_2m_max,temperature_2m_min',
        'temperature_unit': 'fahrenheit' if config.weather_report_units != 'metric' else 'celsius',
        'wind_speed_unit': 'mph' if config.weather_report_units != 'metric' else 'kmh',
        'precipitation_unit': 'inch' if config.weather_report_units != 'metric' else 'mm'
    })

    if response.status_code != 200:
        return Response(response.status_line, mimetype = 'text/plain'), 500

    weather_report = response.json()

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneText>\n'
           '  <Title>Weather Report</Title>\n'
           '  <Text>')

    xml += escape('Temperature is {0}{1}'.format(
        weather_report['current']['temperature_2m'],
        weather_report['current_units']['temperature_2m'][1:]
    ))

    if weather_report['current']['apparent_temperature'] != weather_report['current']['temperature_2m']:
        xml += escape(' (feels like {0}{1})'.format(
            weather_report['current']['apparent_temperature'],
            weather_report['current_units']['apparent_temperature'][1:]
        ))

    xml += escape(' with a low of {0}{1} and a high of {2}{3}.\n\nRainfall is {4}{5}'.format(
        weather_report['daily']['temperature_2m_min'][0],
        weather_report['daily_units']['temperature_2m_min'][1:],
        weather_report['daily']['temperature_2m_max'][0],
        weather_report['daily_units']['temperature_2m_max'][1:],
        weather_report['current']['precipitation'],
        weather_report['current_units']['precipitation'],
    ))

    if weather_report['current']['precipitation_probability']:
        xml += escape(' with a {0}{1} chance of rain'.format(
            weather_report['current']['precipitation_probability'],
            weather_report['current_units']['precipitation_probability']
        ))

    xml += escape(' and a pressure of {0}{1}.\n\nWind is {2}{3} from the {4} with gusts of up to {5}{6}.'.format(
        weather_report['current']['surface_pressure'],
        weather_report['current_units']['surface_pressure'],
        weather_report['current']['wind_speed_10m'],
        weather_report['current_units']['wind_speed_10m'],
        ['north', 'northeast', 'east', 'southeast',
         'south', 'southwest', 'west', 'northwest'][int((weather_report['current']['wind_direction_10m'] + 22.5) / 45) % 8],
        weather_report['current']['wind_gusts_10m'],
        weather_report['current_units']['wind_gusts_10m']
    ))

    xml += '</Text>\n'

    if g.is_79xx:
        xml += '  <Prompt>Your current options</Prompt>\n'

    xml += ('  <SoftKeyItem>\n'
            '    <Name>Exit</Name>\n'
            '    <Position>' + ('3' if g.is_79xx else '1') + '</Position>\n'
            '    <URL>' + request.url_root + 'services</URL>\n'
            '  </SoftKeyItem>\n'
            '  <SoftKeyItem>\n'
            '    <Name>Refresh</Name>\n'
            '    <Position>' + ('1' if g.is_79xx else '2') + '</Position>\n'
            '    <URL>SoftKey:Update</URL>\n'
            '  </SoftKeyItem>\n'
            '</CiscoIPPhoneText>\n')

    return Response(xml, mimetype = 'text/xml'), 200


@blueprint.route('/services/88xx')
def menu_item():
    # 88xx series need a menu item before the index
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<CiscoIPPhoneMenu>\n'
           '  <Title>Services</Title>\n'
           '  <MenuItem>\n'
           '    <Name>Services</Name>\n'
           '    <URL>' + request.url_root + 'services</URL>\n'
           '  </MenuItem>\n'
            '</CiscoIPPhoneMenu>\n')

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
