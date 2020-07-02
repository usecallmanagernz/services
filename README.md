# Services

This repository contains example phone XML services as a WSGI application
written in Python/Flask.

Endpoints provided are:

* /authentication - Authentication for CGI/Execute requests to the phone.
* /services - Simple menu that can show the currently parked calls.
* /directory - Local directory that uses voicemail.conf.
* /directory/79xx - 7900 series need MenuItem before loading /directory.
* /problem-report - 7800 and 8800 series problem report upload.

Settings for the application are loaded from `config.yml`, the location of
this file can be changed by setting the `SERVICES_CONFIG` environment
variable.

Additional settings for Flask can be specified in the `FLASK_CONFIG`
environment variable.

See [http://usecallmanager.nz/phone-services-xml.html](Phone Services) for
more information.
