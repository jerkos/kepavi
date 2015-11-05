# -*- coding: utf-8 -*-
"""
    flaskbb.emails
    ~~~~~~~~~~~~~~~~~~~~

    This module adds the functionality to send emails

    :copyright: (c) 2014 by the FlaskBB Team.
    :license: BSD, see LICENSE for more details.
"""
import os

from flask import render_template
from postmark import PMMail

try:
    from kepavi.private_keys import POSTMARK
except ImportError:
    POSTMARK = os.environ.get('POSTMARK_API_TOKEN')


def send_reset_token(user, token):
    send_email(
        subject="[metabomatch: password reset]",
        recipients=[user.email],
        text_body=render_template(
            "email/reset_password.txt",
            user=user,
            token=token
        ),
        html_body=render_template(
            "email/reset_password.html",
            user=user,
            token=token
        )
    )


def send_reply_notification(users, topic_title, link):
    send_email(
        subject="[metabomatch: new reply]",
        recipients=[u.email for u in users],
        text_body=render_template(
            "email/reply_notification.txt",
            topic_title=topic_title,
            link=link
        ),
        html_body=render_template(
            "email/reply_notification.html",
            topic_title=topic_title,
            link=link
        )
    )


def send_email(subject, recipients, text_body, html_body, sender='contact@metabomatch.com'):
    message = PMMail(api_key=POSTMARK,
                     subject=subject,
                     sender=sender,
                     text_body=text_body,
                     html_body=html_body,
                     track_opens=True,
                     to=",".join(recipients)
                     )
    message.send()
