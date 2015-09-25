# -*- coding: utf-8 -*-
"""
    flaskbb.app
    ~~~~~~~~~~~~~~~~~~~~

    manages the app creation and configuration process

    :copyright: (c) 2014 by the FlaskBB Team.
    :license: BSD, see LICENSE for more details.
"""
from kepavi.auth.forms import LoginForm
from kepavi.helpers import format_date, time_since, older_than_one_month, time_left_to, is_online, crop_title, quote
from kepavi.user.models import User
from kepavi.user.views import user

try:
    from metabomatch.private_keys import GITHUB_CLIENT_SECRET
except ImportError:
    GITHUB_CLIENT_SECRET = ''

import os
import logging
import datetime
import sys

from flask import Flask, request, render_template
from flask_login import current_user

# Import the auth blueprint
from kepavi.auth.views import auth
from kepavi.home.views import home

# extensions
from kepavi.extensions import db, login_manager, cache, migrate, github, csrf, gravatar, babel, oauth


def create_app(config=None):
    """Creates the app."""
    # Initialize the app
    app = Flask("Kepavi")

    # Use the default config and override it afterwards
    app.config.from_object('kepavi.configs.default.DefaultConfig')
    # Update the config
    app.config.from_object(config)
    # try to update the config via the environment variable
    app.config.from_envvar("FLASKBB_SETTINGS", silent=True)

    # github extensions, TODO put that into configs directory
    app.config['GITHUB_CLIENT_ID'] = 'ed057c9e07f531f0fdb6'
    app.config['GITHUB_CLIENT_SECRET'] = os.environ.get('GITHUB_CLIENT_SECRET') or GITHUB_CLIENT_SECRET

    configure_blueprints(app)

    configure_extensions(app)

    configure_template_filters(app)

    # configure_context_processors(app)

    #configure_before_handlers(app)

    configure_errorhandlers(app)

    #configure_logging(app)

    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.INFO)
    return app


def configure_blueprints(app):
    app.register_blueprint(home, url_prefix='/')
    app.register_blueprint(user, url_prefix='/user')
    app.register_blueprint(auth, url_prefix=app.config["AUTH_URL_PREFIX"])


def configure_extensions(app):
    """
    Configures the extensions
    """

    # Flask-SQLAlchemy
    db.init_app(app)

    # Flask-Migrate
    migrate.init_app(app, db)

    # Flask-Cache
    cache.init_app(app)

    # Flask-Login
    login_manager.login_view = app.config["LOGIN_VIEW"]
    login_manager.refresh_view = app.config["REAUTH_VIEW"]

    @login_manager.user_loader
    def load_user(user_id):
        """
        Loads the user. Required by the `login` extension
        """
        u = User.query.filter(User.id == user_id).first()
        return u

    login_manager.init_app(app)

    #  github extension
    github.init_app(app)

    # csrf
    csrf.init_app(app)

    # gravatar init
    gravatar.init_app(app)

    babel.init_app(app)

    oauth.init_app(app)


def configure_template_filters(app):
    """
    Configures the template filters
    """
    app.jinja_env.filters['format_date'] = format_date
    app.jinja_env.filters['time_since'] = time_since
    app.jinja_env.filters['older_than_one_month'] = older_than_one_month
    app.jinja_env.filters['time_left_to'] = time_left_to
    app.jinja_env.filters['is_online'] = is_online
    app.jinja_env.filters['crop_title'] = crop_title
    app.jinja_env.filters['quote'] = quote


def configure_before_handlers(app):
    """
    Configures the before request handlers
    """

    @app.before_request
    def update_lastseen():
        """
        Updates `lastseen` before every reguest if the user is authenticated
        """
        if current_user.is_authenticated():
            current_user.lastseen = datetime.datetime.utcnow()
            db.session.add(current_user)
            db.session.commit()


def configure_errorhandlers(app):
    """
    Configures the error handlers
    """

    @app.errorhandler(403)
    def forbidden_page(error):
        return render_template("errors/forbidden_page.html", form=LoginForm()), 403

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/page_not_found.html", form=LoginForm()), 404

    @app.errorhandler(500)
    def server_error_page(error):
        return render_template("errors/server_error.html", form=LoginForm()), 500


def configure_logging(app):
    """
    Configures logging.
    """

    logs_folder = os.path.join(app.root_path, os.pardir, "logs")
    from logging.handlers import SMTPHandler
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]')

    info_log = os.path.join(logs_folder, app.config['INFO_LOG'])

    info_file_handler = logging.handlers.RotatingFileHandler(
        info_log,
        maxBytes=100000,
        backupCount=10
    )

    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(formatter)
    app.logger.addHandler(info_file_handler)

    error_log = os.path.join(logs_folder, app.config['ERROR_LOG'])

    error_file_handler = logging.handlers.RotatingFileHandler(
        error_log,
        maxBytes=100000,
        backupCount=10
    )

    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    app.logger.addHandler(error_file_handler)

    if app.config["SEND_LOGS"]:
        mail_handler = \
            SMTPHandler(app.config['MAIL_SERVER'],
                        app.config['MAIL_DEFAULT_SENDER'],
                        app.config['ADMINS'],
                        'application error, no admins specified',
                        (
                            app.config['MAIL_USERNAME'],
                            app.config['MAIL_PASSWORD'],
                        ))

        mail_handler.setLevel(logging.ERROR)
        mail_handler.setFormatter(formatter)
        app.logger.addHandler(mail_handler)

if __name__ == '__main__':
    create_app().run(debug=True)
