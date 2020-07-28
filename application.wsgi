#!/usr/bin/python3

from flask import Flask, Response
import authentication
import services
import directory
import problem_report


application = Flask(__name__)
application.config.from_envvar('FLASK_CONFIG', silent = True)

application.register_blueprint(authentication.blueprint)
application.register_blueprint(services.blueprint)
application.register_blueprint(directory.blueprint)
application.register_blueprint(problem_report.blueprint)


@application.route('/')
def index():
    return Response('', mimetype = 'text/plain'), 200


@application.errorhandler(Exception)
def error_handler(error):
    return Response(str(error), mimetype = 'text/plain'), 500


if __name__ == '__main__':
    application.run()
