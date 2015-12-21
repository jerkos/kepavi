# -*- coding: utf-8 -*-
"""
    kepavi.user.views
    ~~~~~~~~~~~~~~~~~~~~

    The user view handles the user profile
    and the user settings from a signed in user.

    :license: BSD, see LICENSE for more details.
"""
import json
import logging
# import cobra
# from kepavi.biomodels import BiomodelMongo
from kepavi.cobra_utils import _launch_fba, build_kegg_network_mixed,\
                               _build_genome_scale_network
from kepavi.kegg_utils import Kegg, Organism
from kepavi.utils import s3_upload_from_server, download_from_s3
from kepavi.private_keys import S3_URL
import os
# from datetime import datetime

from kepavi.user.forms import CreateProjectForm, CreateFBAAnalysisForm
from kepavi.user.models import Project, Analysis, User, Biomodel
from kepavi.auth.forms import LoginForm

import requests
from flask import Blueprint, flash, request, redirect, url_for, render_template, Response
from flask_login import login_required, current_user

from requests.packages.urllib3.exceptions import ConnectionError


user = Blueprint("user", __name__, template_folder="../templates")


@user.route("/<username>")
@login_required
def profile(username):
    form = CreateProjectForm()
    return render_template('user/profile.html', create_project_form=form, display_sidebar=True)


@user.route('/<username>/<int:project_id>-<slug>')
@login_required
def project(username, project_id, slug):
    p = Project.query.filter(Project.id == project_id).first_or_404()
    return render_template('user/project.html', project=p, display_sidebar=True)


@user.route('/<username>/create_project', methods=['POST'])
@login_required
def create_project(username):
    form = CreateProjectForm(request.form)
    if form.validate_on_submit():
        p = Project(title=form.title.data, user_id=current_user.id)
        p.save()
        return redirect(url_for('user.profile',
                                username=current_user.username))
    return render_template('errors/server_error.html', form=LoginForm())


@user.route('/<username>/<int:project_id>-<slug>/create_fba_analysis')
@login_required
def create_fba_analysis(username, project_id, slug):
    u = User.query.filter(User.username == username).first_or_404()
    form = CreateFBAAnalysisForm()
    form.set_models(u)
    p = Project.query.filter(Project.id == project_id).first_or_404()
    return render_template('user/create_fba_analysis.html',
                           form=form,
                           project=p,
                           display_sidebar=True)


@user.route('/<username>/get_sbml_reactions')
@login_required
def get_sbml_reactions(username):
    model_name = request.args.get('model_name')
    if not model_name:
        flash("An error occured", 'error')
        return redirect(request.referrer)
    # u = User.query.filter(User.username == username).first_or_404()
    model = Biomodel.query.filter(Biomodel.name == model_name).first_or_404()

    # for the moment this not allowed
    # model = [b for b  in u.biomodels_diffs if b.title == model_name][0]
    # if model is None:
    #     return render_template('errors/page_not_found.html')

    logging.info('loading model from mongodb...')
    # TODO get the sbml model from mongodb
    sbml_model = model.get_cobra_model()
    if sbml_model is None:
        return render_template('errors/server_error.html', form=LoginForm())
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

    logging.debug(data)

    model_name = data['model']
    project_id = data['project_id']
    title = data['title']

    model = Biomodel.query.filter(Biomodel.name == model_name).first_or_404()

    # have often exception here du to encoding issues
    sbml_model = model.get_cobra_model()
    if sbml_model is None:
        return render_template('errors/server_error.html', form=LoginForm())

    solution = _launch_fba(sbml_model,
                           data['objective_functions'],
                           data['constraints'])

    # create analysis object
    a = Analysis(title=data['title'],
                 kind=Analysis.KIND[0],
                 model_id=model.id,
                 project_id=project_id)
    a.results_content = solution.status
    a.serialized_properties = json.dumps(data)
    # in order to populate its id field
    a.save()

    # building several path local and s3 path
    filename = "{}-{}-{}".format(username, project_id, a.id)
    results_url = filename.replace('-', '/')

    # dump solution to file
    d = {'status': solution.status, 'objective_value': solution.f,
         'x_dict': solution.x_dict, 'y_dict': solution.y_dict}

    with open(filename, 'w') as f:
        f.write(json.dumps(d).encode('utf-8'))

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


@user.route("/<username>/visualize/<int:analysis_id>")
@login_required
def visualize_fba_analysis(username, analysis_id):
    """
    main endpoint to visualize flux balance analysis

    """
    analysis = Analysis.query.filter(Analysis.id == analysis_id).first_or_404()

    # retrieve file data from s3
    filename = '{}/{}/{}'.format(username, analysis.project_id, analysis_id)
    resp = requests.get(S3_URL + filename)

    # return error code if request failed
    if resp.status_code != 200:
        return render_template('errors/server_error.html'), 500

    orgs = Organism.query.order_by(Organism.tax).all()

    model = analysis.model
    model_name = model.name
    pathways = Kegg.get_pathways_list(org=model.kegg_org)
    return render_template('user/fba_analysis.html',
                           analysis=analysis, organisms=orgs,
                           model_name=model_name, pathways=pathways,
                           display_sidebar=False)


@user.route('/<username>/get_kegg_pathways', methods=['GET'])
def get_kegg_pathways(username):
    org = request.args.get('org', 'hsa')  # the default will be the human.
    pathways = Kegg.get_pathways_list(org)
    data = json.dumps(pathways)
    return data


@user.route('/<username>/get_kgml', methods=['GET'])
@login_required
def get_kgml(username):
    """
    main function to visualize network
    return json encoded graph
    """

    pathway_id = request.args.get('pathway_id')
    if pathway_id is None:
        return json.dumps([])

    analysis_id = request.args.get('analysis_id')
    analysis = Analysis.query.filter(Analysis.id == analysis_id).first_or_404()

    # retrieve file data from s3
    filename = '{}/{}/{}'.format(username, analysis.project_id, analysis_id)
    try:
        resp = requests.get(S3_URL + filename)
    except ConnectionError:
        return render_template('errors/server_error.html', form=LoginForm())
    # return error code if request failed
    if resp.status_code != 200:
        return render_template('errors/server_error.html', form=LoginForm())

    # load fba analysis results
    results = json.loads(resp.text)

    # get the sbml model
    model = analysis.model.get_cobra_model()
    if model is None:
        return render_template('errors/server_error.html')

    if pathway_id == 'whole':
        # whole drawing requested
        cytoscape_formatted = _build_genome_scale_network(model, results)

    else:
        kegg_model = Kegg.get_kgml_obj(pathway_id)

        if model is None or kegg_model is None:
            return render_template('errors/page_not_found.html', form=LoginForm())

        kegg_model_name = request.args.get('pathway_name')
        cytoscape_formatted = build_kegg_network_mixed(kegg_model,
                                                       kegg_model_name,
                                                       model,
                                                       results)
    return json.dumps(cytoscape_formatted)


@user.route('/<username>/download/<project_id>/<analysis_id>')
@login_required
def download(username, project_id, analysis_id):
    filename = '{}/{}/{}'.format(username, project_id, analysis_id)
    text = download_from_s3(S3_URL, filename)
    if text is None:
        return render_template('errors/server_error.html', form=LoginForm())
    f = filename.replace('/', '-') + '.json'
    return Response(text,
                    mimetype='application/json',
                    headers={'Content-Disposition': 'attachment;filename=' + f}
                    )
