![GitHub Workflow Status (branch)](https://img.shields.io/github/workflow/status/usecallmanagernz/services/python%20lint/master?label=python%20lint) ![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/usecallmanagernz/services?color=blue&label=version&sort=semver)

# XML Services

This repository contains example phone XML services as a WSGI application
written in Python/Flask.

Endpoints provided are:

* `/authentication` - Authentication for CGI/Execute requests to the phone.
* `/services` - Simple menu that can show the currently parked calls.
* `/directory` - Local directory that uses voicemail.conf.
* `/directory/79xx` - 7900 series need MenuItem before loading /directory.
* `/problem-report` - 7800 and 8800 series problem report upload.

Settings for the application are loaded from `config.yml`, the location of
this file can be changed by setting the `SERVICES_CONFIG` environment
variable.

Additional settings for Flask can be specified in the `FLASK_CONFIG`
environment variable.

See [Phone Services](http://usecallmanager.nz/phone-services-xml.html) for
more information.

## Requirements

The following non-standard Python modules are required: `requests` and `Flask`.

You can use the packages provided by your OS distribution or run
`sudo pip3 install -r requirements.txt` to satisfy those dependancies.
