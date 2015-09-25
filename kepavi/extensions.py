# -*- coding: utf-8 -*-

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cache import Cache
from flask_migrate import Migrate
from flask_github import GitHub
from flask_htmlmin import HTMLMIN
from flask_wtf.csrf import CsrfProtect
from flask_gravatar import Gravatar
from flask_babel import Babel
from flask_oauthlib.client import OAuth

# Database
db = SQLAlchemy()

# Login
login_manager = LoginManager()

# Caching
cache = Cache()

# Migrations
migrate = Migrate()

# performing API call to github
github = GitHub()

gravatar = Gravatar(default='identicon')

# csrf protection
csrf = CsrfProtect()

babel = Babel()

htmlminify = HTMLMIN()

#  twitter oauth
oauth = OAuth()
