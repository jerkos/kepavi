# -*- coding: utf-8 -*-
"""
    flaskbb.configs.default
    ~~~~~~~~~~~~~~~~~~~~~~~

    This is the default configuration for FlaskBB that every site should have.
    You can override these configuration variables in another class.

    :copyright: (c) 2014 by the FlaskBB Team.
    :license: BSD, see LICENSE for more details.
"""
import os


class DefaultConfig(object):

    DEBUG = True
    # TESTING = True

    _basedir = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(
                            os.path.dirname(__file__)))))
    ## Database
    # If no SQL service is choosen, it will fallback to sqlite
    # For PostgresSQL:
    try:
        SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']  # "postgresql://localhost/example"
    # For SQLite:
    except KeyError:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + _basedir + '/' + 'kepavi.sqlite'
        DEBUG = True
        # TESTING = True

    ## Security
    # This is the secret key that is used for session signing.
    # You can generate a secure key with os.urandom(24)
    SECRET_KEY = os.urandom(24)  # 'secret key'

    # You can generate the WTF_CSRF_SECRET_KEY the same way as you have
    # generated the SECRET_KEY. If no WTF_CSRF_SECRET_KEY is provided, it will
    # use the SECRET_KEY.
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.urandom(24)  # "reallyhardtoguess"

    # Auth
    LOGIN_VIEW = "auth.login"
    REAUTH_VIEW = "auth.reauth"
    LOGIN_MESSAGE_CATEGORY = "error"

    # html minify
    #MINIFY_PAGE = True

    # flask_compress
    COMPRESS_LEVEL = 9

    # Caching
    # For all available caching types, take a look at the Flask-Cache docs
    # https://pythonhosted.org/Flask-Cache/#configuring-flask-cache
    CACHE_TYPE = "simple"
    CACHE_DEFAULT_TIMEOUT = 60

    # Captcha
    # To get recaptcha, visit the link below:
    # https://www.google.com/recaptcha/admin/create
    RECAPTCHA_ENABLED = False
    RECAPTCHA_USE_SSL = False
    RECAPTCHA_PUBLIC_KEY = "your_public_recaptcha_key"
    RECAPTCHA_PRIVATE_KEY = "your_private_recaptcha_key"
    RECAPTCHA_OPTIONS = {"theme": "white"}

    ## Mail
    # Local SMTP Server
    #MAIL_SERVER = "localhost"
    #MAIL_PORT = 25
    #MAIL_USE_SSL = False
    #MAIL_USERNAME = ""
    #MAIL_PASSWORD = ""
    #MAIL_DEFAULT_SENDER = "noreply@example.org"

    # Google Mail Example
    # MAIL_SERVER = "smtp.live.com"
    # MAIL_PORT = 587
    # MAIL_USE_TLS = True
    # MAIL_USERNAME = "cram@hotmail.fr"
    # MAIL_PASSWORD = "marco##1986"
    # MAIL_DEFAULT_SENDER = "contact@metabomatch.com"  # ("Marco from metabomatch", "marc.dubois@omics-services.com")

    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USERNAME = "marc.dubois.omics.services@gmail.com"
    MAIL_PASSWORD = "Marco@1986"
    MAIL_DEBUG = False
    MAIL_DEFAULT_SENDER = "contact@metabomatch.com"  # ("metabomatch informations", "contact@metabomatch.com")

    # The user who should recieve the error logs
    ADMINS = ["cram@hotmail.fr"]

    ## Error/Info Logging
    # If SEND_LOGS is set to True, the admins (see the mail configuration) will
    # recieve the error logs per email.
    SEND_LOGS = False

    # The filename for the info and error logs. The logfiles are stored at
    # flaskbb/logs
    INFO_LOG = "info.log"
    ERROR_LOG = "error.log"

    # Flask-Redis
    REDIS_ENABLED = False
    REDIS_URL = "redis://:password@localhost:6379"
    REDIS_DATABASE = 0

    # URL Prefixes.
    FORUM_URL_PREFIX = "/discuss"
    USER_URL_PREFIX = "/user"
    AUTH_URL_PREFIX = "/auth"
    ADMIN_URL_PREFIX = "/admin"

