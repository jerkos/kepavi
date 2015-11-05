# -*- coding: utf-8 -*-
"""
    flaskbb.user.models
    ~~~~~~~~~~~~~~~~~~~~

    This module provides the models for the user.

    :copyright: (c) 2014 by the FlaskBB Team.
    :license: BSD, see LICENSE for more details.
"""
from datetime import datetime
import logging

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from kepavi.biomodels import BiomodelMongo
from kepavi.helpers import slugify
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from flask_login import UserMixin
import uuid

import cobra.io

from kepavi._compat import max_integer
from kepavi.extensions import db, cache, github
from kepavi.utils import random_email


class InsertableMixin(object):

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

    def delete(self):
        db.session.delete(self)
        db.session.commit()
        return self


class BiomodelModification(db.Model, InsertableMixin):
    __tablename__ = 'biomodels_diffs'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    biomodel_id = db.Column(db.Integer, db.ForeignKey('biomodels.id'))
    diff = db.Column(db.Text)  # stored in json

    user = db.relationship('User', foreign_keys=[user_id], backref='biomodels_diffs')
    biomodel = db.relationship('Biomodel', foreign_keys=[biomodel_id], backref='biomodels_diffs')


class Biomodel(db.Model, InsertableMixin):
    __tablename__ = 'biomodels'

    id = db.Column(db.Integer, primary_key=True)

    # a name provided by the user creator
    # should be the same one stored in mongodb if kegg_org is left
    # empty
    name = db.Column(db.String(200), nullable=False, unique=True)

    # if this model represents a model coming from BioModels Whole Genome
    # this should be filled
    kegg_org = db.Column(db.String(10), nullable=True)

    insertion_date = db.Column(db.DateTime, default=datetime.utcnow())

    # coming from BioModels: layout is not yet available but may be fix`ed`
    # in next BioModels releases
    layout_available = db.Column(db.Boolean, default=False)

    fbc_availabale = db.Column(db.Boolean, default=True)

    def get_cobra_model(self):

        if self.kegg_org is not None:
            model = BiomodelMongo.objects(organism=self.kegg_org).first()
        else:
            model = BiomodelMongo.objects(name=self.name).first()

        # try to load the cobra model
        cobra_model = None
        try:
            cobra_model = cobra.io._from_dict(model.cobra_model)
        except Exception as e:
            logging.error(e)
        return cobra_model


class Analysis(db.Model, InsertableMixin):
    __tablename__ = 'analysis'
    KIND = ('Flux balance analysis', 'Annotation & Database search')

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    kind = db.Column(db.String(200), default=KIND[0])
    creation_date = db.Column(db.DateTime, default=datetime.utcnow())

    results_url = db.Column(db.String(200))
    results_content = db.Column(db.Text)

    model_id = db.Column(db.Integer, db.ForeignKey('biomodels.id'))
    model = db.relationship('Biomodel', foreign_keys=[model_id], backref='analysis')

    # may be used to sotre analysis parameters as json properties
    serialized_properties = db.Column(db.Text)

    model_diff_id = db.Column(db.Integer, db.ForeignKey('biomodels_diffs.id'), nullable=True)
    model_diff = db.relationship('BiomodelModification', foreign_keys=[model_diff_id], backref='analysis')

    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    project = db.relationship('Project', foreign_keys=[project_id], backref='analysis')

    @property
    def slug(self):
        return slugify(self.title)


class Project(db.Model, InsertableMixin):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow())

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    user = db.relationship('User', foreign_keys=[user_id], backref='projects')

    @property
    def slug(self):
        return slugify(self.title)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    __searchable__ = ['username', 'email']

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(200), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)

    # logged with github api, is nullable
    github_access_token = db.Column(db.String(200))

    twitter_access_token = db.Column(db.String(200))
    twitter_secret_token = db.Column(db.String(200))

    _password = db.Column('password', db.String(120), nullable=False)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow())
    lastseen = db.Column(db.DateTime, default=datetime.utcnow())
    avatar = db.Column(db.String(200))

    @staticmethod
    def create_from_twitter_oauth(resp):
        """
        :param resp: twitter response.
        :return: newly created user after database insertion.
        """

        u = User()
        u.username = resp['screen_name']
        u.password = uuid.uuid4()
        u.email = random_email()
        u.date_joined = datetime.utcnow()
        u.twitter_access_token = resp['oauth_token']
        u.twitter_secret_token = resp['oauth_token_secret']
        return u.save()

    @property
    def days_registered(self):
        """Returns the amount of days the user is registered."""

        days_registered = (datetime.utcnow() - self.date_joined).days
        if not days_registered:
            return 1
        return days_registered

    # Methods
    def __repr__(self):
        """Set to a unique key specific to the object in the database.
        Required for cache.memoize() to work across requests.
        """

        return "<{} {}>".format(self.__class__.__name__, self.username)

    def _get_password(self):
        """Returns the hashed password"""

        return self._password

    def _set_password(self, password):
        """Generates a password hash for the provided password"""

        self._password = generate_password_hash(password)

    # Hide password encryption by exposing password field only.
    password = db.synonym('_password',
                          descriptor=property(_get_password,
                                              _set_password))

    def check_password(self, password):
        """Check passwords. If passwords match it returns true, else false"""

        if self.password is None:
            return False
        return check_password_hash(self.password, password)

    @classmethod
    def authenticate(cls, login, password):
        """A classmethod for authenticating users
        It returns true if the user exists and has entered a correct password

        :param login: This can be either a username or a email address.

        :param password: The password that is connected to username and email.
        """

        user = cls.query.filter(db.or_(User.username == login,
                                       User.email == login)).first()

        if user:
            authenticated = user.check_password(password)
        else:
            authenticated = False
        return user, authenticated

    @staticmethod
    def _make_token(data, timeout):
        s = Serializer(current_app.config['SECRET_KEY'], timeout)
        return s.dumps(data)

    @staticmethod
    def _verify_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        data = None
        expired, invalid = False, False
        try:
            data = s.loads(token)
        except SignatureExpired:
            expired = True
        except Exception:
            invalid = True
        return expired, invalid, data

    def make_reset_token(self, expiration=3600):
        """Creates a reset token. The duration can be configured through the
        expiration parameter.

        :param expiration: The time in seconds how long the token is valid.
        """

        return self._make_token({'id': self.id, 'op': 'reset'}, expiration)

    def verify_reset_token(self, token):
        """Verifies a reset token. It returns three boolean values based on
        the state of the token (expired, invalid, data)

        :param token: The reset token that should be checked.
        """

        expired, invalid, data = self._verify_token(token)
        if data and data.get('id') == self.id and data.get('op') == 'reset':
            data = True
        else:
            data = False
        return expired, invalid, data

    def save(self):
        """Saves a user. If a list with groups is provided, it will add those
        to the secondary groups from the user.

        :param groups: A list with groups that should be added to the
                       secondary groups from user.
        """

        db.session.add(self)
        db.session.commit()
        return self

    def delete(self):
        """Deletes the User."""

        db.session.delete(self)
        db.session.commit()

        return self
