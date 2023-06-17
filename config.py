#!/usr/bin/env python3
#
# Copyright (c) 2020 Gareth Palmer <gareth.palmer3@gmail.com>
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.

import os.path
import yaml


tftpboot_dir = '/var/lib/tftpboot'
reports_dir = '/var/log/cisco'

cgi_username = 'cisco'
cgi_password = 'cisco'

manager_url = 'http://localhost:8088/mxml'
manager_username = 'asterisk'
manager_secret = 'asterisk'

config_file = os.environ.get('SERVICES_CONFIG', 'config.yml')

if os.path.exists(config_file):
    with open(config_file, 'r', encoding = 'UTF-8') as file:
        document = yaml.safe_load(file)

        if document:
            tftpboot_dir = document.get('tftpboot-dir', tftpboot_dir)
            reports_dir = document.get('reports-dir', reports_dir)

            cgi_username = document.get('cgi-username', cgi_username)
            cgi_password = document.get('cgi-password', cgi_password)

            manager_url = document.get('manager-url', manager_url)
            manager_username = document.get('manager-username', manager_username)
            manager_secret = document.get('manager-secret', manager_secret)
