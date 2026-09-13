#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import os.path
import yaml


manager_url = 'http://localhost:8088/mxml'
manager_username = 'asterisk'
manager_secret = 'asterisk'

cgi_username = 'cisco'
cgi_password = 'cisco'

busy_extensions = ''
night_mode = ''

weather_report_latitude = ''
weather_report_longitude = ''
weather_report_units = 'metric'

reports_dir = '/var/log/cisco'

config_file = os.environ.get('SERVICES_CONFIG', 'config.yml')

if os.path.exists(config_file):
    with open(config_file, 'r', encoding = 'UTF-8') as file:
        document = yaml.safe_load(file)

        if document:
            manager_url = document.get('manager-url', manager_url)
            manager_username = document.get('manager-username', manager_username)
            manager_secret = document.get('manager-secret', manager_secret)

            cgi_username = document.get('cgi-username', cgi_username)
            cgi_password = document.get('cgi-password', cgi_password)

            busy_extensions = document.get('busy-extensions', busy_extensions)
            night_mode = document.get('night-mode', night_mode)

            weather_report_latitude = document.get('weather-report-latitude', weather_report_latitude)
            weather_report_longitude = document.get('weather-report-longitude', weather_report_longitude)
            weather_report_units = document.get('weather-report-units', weather_report_units)

            reports_dir = document.get('reports-dir', reports_dir)
