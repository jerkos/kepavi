import json

from flask import Blueprint, url_for, redirect, render_template, request, jsonify
from kepavi.auth.forms import LoginForm
from kepavi.kegg_utils import Organism, Kegg
from sqlalchemy import desc

from kepavi.extensions import db
from kepavi.user.models import User


home = Blueprint('home', __name__, template_folder='../templates')


@home.route('')
def index():
    form = LoginForm()
    return render_template('home/home_layout.html', form=form)


@home.route('visualization', methods=['GET'])
def visualization():
    orgs = Organism.query.order_by(Organism.tax).all()
    return render_template('home/visualization.html', organisms=orgs)


@home.route('get-pathways', methods=['GET'])
def get_pathways():
    org = request.args.get('org', 'hsa')  # the default will be the human.
    pathways = Kegg.get_pathways_list(org)
    data = json.dumps(pathways)
    return data


@home.route('get-kgml', methods=['GET'])
def get_kgml():
    pathway_id = request.args.get('pathway_id')
    if pathway_id is None:
        return []
    cytoscape_formatted = Kegg.get_kgml(pathway_id)
    j = json.dumps(cytoscape_formatted)
    return j

@home.route('about', methods=['GET'])
def about():
    return render_template('home/about.html')


@home.route('faq', methods=['GET'])
def faq():
    return render_template('home/FAQ.html')
