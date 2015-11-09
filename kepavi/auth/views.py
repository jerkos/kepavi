# -*- coding: utf-8 -*-
"""
    auth.views
    This view provides user authentication, registration and a view for
    resetting the password of a user if he has lost his password

"""

import os

from flask import Blueprint, flash, redirect, url_for, request, current_app, session, render_template
from flask_login import current_user, login_user, login_required, logout_user, confirm_login, login_fresh

from kepavi.extensions import github, oauth
from kepavi.email import send_reset_token
from kepavi.auth.forms import LoginForm, ReauthForm, ForgotPasswordForm, ResetPasswordForm
from kepavi.user.models import User

try:
    from kepavi.private_keys import TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET
except ImportError:
    TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET = None, None


auth = Blueprint("auth", __name__, template_folder="../templates")


# Use Twitter as example remote application
twitter = oauth.remote_app('twitter',
                           # unless absolute urls are used to make requests, this will be added
                           # before all URLs.  This is also true for request_token_url and others.
                           base_url='https://api.twitter.com/1.1/',
                           # where flask should look for new request tokens
                           request_token_url='https://api.twitter.com/oauth/request_token',
                           # where flask should exchange the token with the remote application
                           access_token_url='https://api.twitter.com/oauth/access_token',
                           # twitter knows two authorizatiom URLs.  /authorize and /authenticate.
                           # they mostly work the same, but for sign on /authenticate is
                           # expected because this will give the user a slightly different
                           # user interface on the twitter side.
                           authorize_url='https://api.twitter.com/oauth/authenticate',
                           # the consumer keys from the twitter application registry.
                           consumer_key=TWITTER_CONSUMER_KEY or os.environ.get('TWITTER_CONSUMER_KEY'),
                           consumer_secret=TWITTER_CONSUMER_SECRET or os.environ.get('TWITTER_CONSUMER_SECRET')
                           )


@auth.route("/login", methods=["GET", "POST"])
def login():
    """
    Logs the user in
    """

    if current_user is not None and current_user.is_authenticated():
        return redirect(url_for("user.profile", username=current_user.username))

    form = LoginForm(request.form)
    if form.validate_on_submit():
        user, authenticated = User.authenticate(form.login.data,
                                                form.password.data)
        if user and authenticated:
            # remove this key when a user is authenticated
            # session.pop('nb_views', None)
            login_user(user, remember=form.remember_me.data)
            flash("Welcome onboard {} !".format(user.username), "success")
            return redirect(request.args.get("next") or url_for("user.profile", username=user.username))

        flash("Wrong username or password", "danger")
    return render_template("auth/login.html", form=form)


@auth.route("/reauth", methods=["GET", "POST"])
@login_required
def reauth():
    """
    Reauthenticates a user
    """

    if not login_fresh():
        form = ReauthForm(request.form)
        if form.validate_on_submit():
            confirm_login()
            flash("Reauthenticated", "success")
            return redirect(request.args.get("next") or
                            url_for("user.profile"))
        return render_template("auth/reauth.html", form=form)
    return redirect(request.args.get("next") or
                    url_for("user.profile", username=current_user.username))


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "success")
    return redirect(url_for("home.index"))


@auth.route("/register", methods=["GET", "POST"])
def register():
    """
    Register a new user
    """

    if current_user is not None and current_user.is_authenticated():
        return redirect(url_for("user.profile"))

    if current_app.config["RECAPTCHA_ENABLED"]:
        from kepavi.auth.forms import RegisterRecaptchaForm
        form = RegisterRecaptchaForm(request.form)
    else:
        from kepavi.auth.forms import RegisterForm
        form = RegisterForm(request.form)

    if form.validate_on_submit():
        user = form.save()
        login_user(user)

        flash("Thanks for registering", "success")
        return redirect(url_for("user.profile", username=user.username))
    return render_template("auth/register.html", form_register=form, form=LoginForm())


@auth.route('/resetpassword', methods=["GET", "POST"])
def forgot_password():
    """
    Sends a reset password token to the user.
    """

    if not current_user.is_anonymous():
        return redirect(url_for("forum.index"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            token = user.make_reset_token()
            send_reset_token(user, token=token)

            flash("E-Mail sent! Please check your inbox.", "info")
            return redirect(url_for("auth.forgot_password"))
        else:
            flash(("You have entered an username or email that is not linked \
                with your account"), "danger")
    return render_template("auth/forgot_password.html", form=form)


@auth.route("/resetpassword/<token>", methods=["GET", "POST"])
def reset_password(token):
    """
    Handles the reset password process.
    """

    if not current_user.is_anonymous():
        return redirect(url_for("forum.index"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        expired, invalid, data = user.verify_reset_token(form.token.data)

        if invalid:
            flash("Your password token is invalid.", "danger")
            return redirect(url_for("auth.forgot_password"))

        if expired:
            flash("Your password is expired.", "danger")
            return redirect(url_for("auth.forgot_password"))

        if user and data:
            user.password = form.password.data
            user.save()
            flash("Your password has been updated.", "success")
            return redirect(url_for("auth.login"))

    form.token.data = token
    return render_template("auth/reset_password.html", form=form)


#  github authentication
@auth.route("/login_github")
def login_github():
    return github.authorize()


# twitter authentication
@auth.route('/login_twitter')
def login_twitter():
    callback_url = url_for('auth.twitter_authorized', next=request.args.get('next'))
    return twitter.authorize(callback=callback_url or request.referrer or None)


@auth.route('/twitter-authorized')
def twitter_authorized():
    next_url = request.args.get('next') or url_for('softwares.index')
    resp = twitter.authorized_response()
    if resp is None:
        flash('Twitter login failed !', 'danger')
        return redirect(url_for('softwares.index'))

    user = User.query.filter(User.username == resp['screen_name']).first()
    if user is None:
        user = User.create_from_twitter_oauth(resp)

    login_user(user, True)
    flash("Twitter login succeeded.", "success")
    return redirect(next_url)


@auth.route('/github-callback')
@github.authorized_handler
def authorized(oauth_token):
    next_url = request.args.get('next') or url_for('softwares.index')
    if oauth_token is None:
        flash("Authorization failed.", "danger")
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(github_access_token=oauth_token).first()
    if user is None:
        user = User.create_github_account(oauth_token)

    # session.pop('nb_views', None)
    # force remembering
    login_user(user, True)
    flash("Github login succeeded.", "success")

    return redirect(next_url)


@github.access_token_getter
def token_getter():
    u = User.query.filter(User.id == 1).first()
    return u.github_access_token


@twitter.tokengetter
def get_twitter_token(token=None):
    if current_user.is_authenticated() and current_user.twitter_access_token is not None:
        return current_user.twitter_access_token, current_user.twitter_secret_token
