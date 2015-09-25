# -*- coding: utf-8 -*-
"""
    flaskbb.utils.helpers
    ~~~~~~~~~~~~~~~~~~~~

    A few helpers that are used by flaskbb

    :copyright: (c) 2014 by the FlaskBB Team.
    :license: BSD, see LICENSE for more details.
"""
import re
from datetime import datetime, timedelta

from flask import session, url_for
from flask.ext.login import current_user

from markdown2 import markdown as render_markdown
import unidecode

from kepavi._compat import range_method, text_type

_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')


def slugify(text, delim=u'-'):
    """Generates an slightly worse ASCII-only slug.
    Taken from the Flask Snippets page.

   :param text: The text which should be slugified
   :param delim: Default "-". The delimeter for whitespace
    """

    text = unidecode.unidecode(text)
    result = []
    for word in _punct_re.split(text.lower()):
        if word:
            result.append(word)
    return text_type(delim.join(result))


def crop_title(title, length=None):
    """Crops the title to a specified length

    :param title: The title that should be cropped
    """
    if length is None:
        length = 200
    if len(title) > length:
        return title[:length] + "..."
    return title


def is_online(user):
    """A simple check to see if the user was online within a specified
    time range

    :param user: The user who needs to be checked
    """
    return user.lastseen >= time_diff()


def time_diff():
    """Calculates the time difference between now and the ONLINE_LAST_MINUTES
    variable from the configuration.
    """
    now = datetime.utcnow()
    diff = now - timedelta(minutes=5)
    return diff


def format_date(value, format='%Y-%m-%d'):
    """Returns a formatted time string

    :param value: The datetime object that should be formatted

    :param format: How the result should look like. A full list of available
                   directives is here: http://goo.gl/gNxMHE
    """
    return value.strftime(format)


def time_since(value):
    """Just a interface for `time_delta_format`"""
    return time_delta_format(value)


def time_delta_format(dt, default=None):
    """Returns a string representing time since e.g. 3 days ago, 5 hours ago.
    ref: https://bitbucket.org/danjac/newsmeme/src/a281babb9ca3/newsmeme/
    note: when Babel1.0 is released, use format_timedelta/timedeltaformat
          instead
    """

    if default is None:
        default = 'just now'

    now = datetime.utcnow()
    diff = now - dt

    periods = (
        (diff.days / 365, 'year', 'years'),
        (diff.days / 30, 'month', 'months'),
        (diff.days / 7, 'week', 'weeks'),
        (diff.days, 'day', 'days'),
        (diff.seconds / 3600, 'hour', 'hours'),
        (diff.seconds / 60, 'minute', 'minutes'),
        (diff.seconds, 'second', 'seconds'),
    )

    for period, singular, plural in periods:
        if period < 1:
            continue

        if 1 <= period < 2:
            return u'%d %s ago' % (period, singular)
        else:
            return u'%d %s ago' % (period, plural)

    return default


def older_than_one_month(dt):
    """used to which content is new from old content"""
    now = datetime.utcnow()
    diff = now - dt

    period = diff.days / 30.0
    if period < 1:
        return False
    return True


def time_left_to(date, default_message=None):
    """
    :param date: dd-mm-yyyy
    :return: string
    """
    now = datetime.utcnow()
    diff = date - now

    periods = (
        (diff.days / 365, 'year', 'years'),
        (diff.days / 30, 'month', 'months'),
        (diff.days / 7, 'week', 'weeks'),
        (diff.days, 'day', 'days'),
        (diff.seconds / 3600, 'hour', 'hours'),
        (diff.seconds / 60, 'minute', 'minutes'),
        (diff.seconds, 'second', 'seconds'),
    )

    if default_message is None:
        default_message = 'right now...'

    for period, singular, plural in periods:
        if period < 1:
            continue

        if 1 <= period < 2:
            return u'%d %s left' % (period, singular)
        else:
            return u'%d %s left' % (period, plural)

    return default_message


def quote(string):
    return "'{}'".format(string)
