[![Python Lint](https://img.shields.io/github/actions/workflow/status/usecallmanagernz/services/pylint.yml?branch=master&label=python%20lint)](https://github.com/usecallmanagernz/services/actions/workflows/pylint.yml) [![Version](https://img.shields.io/github/v/tag/usecallmanagernz/services?color=blue&label=version&sort=semver)](https://github.com/usecallmanagernz/services/releases) [![Licence](https://img.shields.io/github/license/usecallmanagernz/services?color=red)](https://github.com/usecallmanagernz/services/blob/master/LICENSE)

# XML Services

This repository contains example phone XML services as a WSGI application
written in Python/Flask.

Endpoints provided are:

* `/authentication` - Authentication for CGI/Execute requests to the phone.
* `/services` - Simple menu that can show the currently parked calls, night
  mode and weather report.
* `/directory` - Local directory that uses voicemail.conf.
* `/messages` - Manage voicemail messages visually (Asterisk 22.11.0 or later).
* `/information` - 7900 series Info button phone help.
* `/problem-report` - 7800 and 8800 series problem report upload.
* `/quality-report` - Record information when QRT in selected.

Settings for the application are loaded from `config.yml`, the location of
this file can be changed by setting the `SERVICES_CONFIG` environment
variable.

Additional settings for Flask can be specified in the `FLASK_CONFIG`
environment variable.

The `messages` endpoint requires additional extensions in the dial
plan for playing messages and greetings.
See [Dialplan Extensions](https://usecallmanager.nz/dialplan-extensions.html#messages)
for more information.

## Requirements

The following non-standard Python modules are required: 'pyyaml', `lxml`
`requests` and `Flask`.

You can use the packages provided by your OS distribution or run
`sudo pip3 install -r requirements.txt` to satisfy those dependancies.

## Installation

The following commands are for Apache on Ubuntu, you may need to adjust some
them for a different distributions.

Copy files and create a virtual-host for services via HTTP:

```
sudo mkdir -p /var/www/services
sudo cp *.py *.wsgi /var/www/services
sudo cp virtualhost.conf /etc/apache2/sites-available/xml-services
sudo a2ensite xml-services
```

Optionally, to enable secure services virtual-host via HTTPS.

```
sudo cp virtualhost-ssl.conf /etc/apache2/sites-available/secure-xml-services
sudo a2ensite secure-xml-services
```

Restart apache.

```
sudo systemctl restart apache2
```

See [HTTP Provisioning](https://usecallmanager.nz/http-provisioning.html#XML-Services)
for more information.

Enable the Asterisk HTTP server in `/etc/asterisk/http.conf`.

```
[general]
enabled=yes
bindaddr=127.0.0.0
bindport=8088
...
```

Enable the Asterisk Manager web interface in  `/etc/asterisk/manager.conf`
and add a user with the credentials from `config.yml`.

```
[general]
...
enabled=yes
webenabled=yes

[asterisk]
secret=asterisk
read=all
...
```

Create a directory to store quality and problem report logs. A different path
may be specified in `config.yml`.

```
mkdir /var/log/cisco
chown www-data:www-data /var/log/cisco
```
