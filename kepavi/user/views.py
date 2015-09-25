# -*- coding: utf-8 -*-
"""
    flaskbb.user.views
    ~~~~~~~~~~~~~~~~~~~~

    The user view handles the user profile
    and the user settings from a signed in user.

    :copyright: (c) 2014 by the FlaskBB Team.
    :license: BSD, see LICENSE for more details.
"""
import json
import logging
import cobra
from kepavi.cobra_utils import get_sbml_from_s3, _launch_fba
from kepavi.utils import s3_upload_from_server
import os
from datetime import datetime

from kepavi.user.forms import ChangePasswordForm, ChangeEmailForm, CreateProjectForm, \
    CreateFBAAnalysisForm  #, ChangeUserDetailsForm
from kepavi.user.models import Project, Analysis, User, Biomodel

import requests
from flask import Blueprint, flash, request, redirect, url_for, render_template
from flask_login import login_required, current_user

from kepavi.extensions import db

try:
    from kepavi.private_keys import TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET
except ImportError:
    TWITTER_CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
    TWITTER_CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')


user = Blueprint("user", __name__, template_folder="templates")


@user.route("/<username>")
@login_required
def profile(username):
    # if not current_user.is_authenticated():
    #     return redirect(url_for('auth.login'))
    form = CreateProjectForm()
    return render_template('user/profile.html', create_project_form=form)


@user.route('/<username>/<int:project_id>-<slug>')
@login_required
def project(username, project_id, slug):
    p = Project.query.filter(Project.id == project_id).first_or_404()
    return render_template('user/project.html', project=p)


@user.route('/<username>/create_project', methods=['POST'])
@login_required
def create_project(username):
    form = CreateProjectForm(request.form)
    if form.validate_on_submit():
        p = Project(title=form.title.data, user_id=current_user.id)
        p.save()
        return redirect(url_for('user.profile', username=current_user.username))


@user.route('/<username>/<int:project_id>-<slug>/create_fba_analysis')
@login_required
def create_fba_analysis(username, project_id, slug):
    u = User.query.filter(User.username == username).first_or_404()
    form = CreateFBAAnalysisForm()
    form.set_models(u)
    p = Project.query.filter(Project.id == project_id).first_or_404()
    return render_template('user/create_fba_analysis.html', form=form, project=p)


@user.route('/<username>/get_reactions')
@login_required
def get_reactions(username):
    model_name = request.args.get('model_name')
    if not model_name:
        flash("An error occured", 'error')
        return redirect(request.referrer)
    u = User.query.filter(User.username == username).first_or_404()
    model = Biomodel.query.filter(Biomodel.name == model_name).first()
    if model is None:
        return render_template('errors/page_not_found.html')
        # for the moment this not allowed
        # model = [b for b  in u.biomodels_diffs if b.title == model_name][0]
        # if model is None:
        #     return render_template('errors/page_not_found.html')
    logging.info('getting sbml model from s3')
    sbml_model = get_sbml_from_s3(model.url)
    d = []
    for r in sbml_model.reactions:
        d.append({
            'name': r.name,
            'lower_bound': r.lower_bound,
            'upper_bound': r.upper_bound,
            'reversibility': r.reversibility,
            'check_mass_balance': not bool(r.check_mass_balance())
        })
    return json.dumps(d)


@user.route('/<username>/launch_fba', methods=['POST'])
@login_required
def launch_fba(username):
    data = request.get_json(force=True)
    print "DATA:", data

    model_name = data['model']
    project_id = data['project_id']
    title = data['title']

    model = Biomodel.query.filter(Biomodel.name == model_name).first_or_404()
    sbml_model = get_sbml_from_s3(model.url)
    solution = _launch_fba(sbml_model, data['objective_functions'], data['constraints'])

    # create analysis object
    a = Analysis(title=data['title'],
                 kind=Analysis.KIND[0],
                 project_id=project_id)
    a.results_content = solution.status

    # in order to populate its id field
    a.save()

    # building several path local and s3 path
    filename = "{}-{}-{}".format(username, project_id, a.id)
    results_url = filename.replace('-', '/')

    # dump solution to file
    d = {'status': solution.status, 'objective_value': solution.f,
         'x_dict': solution.x_dict, 'y_dict': solution.y_dict}

    with open(filename, 'w') as f:
        f.write(json.dumps(d))

    # upload to s3
    logging.info('uploading to s3')
    s3_upload_from_server(filename, destination_filename=results_url)

    # finally save analysis object
    logging.info('saving analysis')
    a.results_url = results_url
    a.save()

    # remove created file
    logging.info('removing created file...')
    try:
        os.remove(filename)
        logging.warn('Done')
    except OSError:
        logging.warn('Enable to remove "{}"'.format(filename))
        logging.warn('Failed !')

    flash('FBA analysis {} saved...'.format(title), 'success')

    return json.dumps({'redirect': url_for('user.profile', username=username)})
    # return redirect(url_for('user.profile', username=current_user.username))


@user.route("/settings/password", methods=["POST", "GET"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_user.password = form.new_password.data
        current_user.save()

        flash("Your password have been updated!", "success")
    return render_template("user/change_password.html", form=form)


@user.route("/settings/email", methods=["POST", "GET"])
@login_required
def change_email():
    form = ChangeEmailForm(current_user)
    if form.validate_on_submit():
        current_user.email = form.new_email.data
        current_user.save()

        flash("Your email have been updated!", "success")
    return render_template("user/change_email.html", form=form)


# @user.route("/settings/user-details", methods=["POST", "GET"])
# @login_required
# def change_user_details():
#     form = ChangeUserDetailsForm(obj=current_user)
#
#     if form.validate_on_submit():
#         form.populate_obj(current_user)
#         current_user.save()
#
#         flash("Your details have been updated!", "success")
#
#     return render_template("user/change_user_details.html", form=form)
