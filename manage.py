import bioservices
from kepavi.biomodels import BiomodelMongo
from kepavi.user.models import User, Biomodel
import os
import csv
import logging

from flask import current_app

try:
    from kepavi.private_keys import GUEST_USER_ID
except ImportError:
    GUEST_USER_ID = os.environ.get('GUEST_USER_ID')

from flask_script import (Manager, Shell, Server)
from flask_migrate import MigrateCommand

from kepavi.app import create_app
from kepavi.extensions import db

# Use the development configuration if available
try:
    from kepavi.configs.development import DevelopmentConfig as Config
except ImportError:
    from kepavi.configs.default import DefaultConfig as Config

from kepavi.kegg_utils import Organism, Kegg

flask_app = create_app(Config)

manager = Manager(flask_app)

# Run local server
manager.add_command("runserver", Server("localhost", port=5000))

# Migration commands
manager.add_command('db', MigrateCommand)


# Add interactive project shell
def make_shell_context():
    return dict(app=current_app, db=db)
manager.add_command("shell", Shell(make_context=make_shell_context))


@manager.command
def initdb():
    """Creates the database."""
    db.create_all()

    logging.info('Getting organism list...')
    l = Kegg.get_org_list()

    logging.info('Insertion begins...')
    d = csv.DictReader(l.split('\n'), delimiter='\t', fieldnames=('code', 'org', 'tax'))
    for row in d:
        o = Organism(row['code'], row['org'], row['tax'])
        o.save()

    u = User(username='marco',email='cram@hotmail.fr', password='Marco@1986')
    u.save()

    b = Biomodel(name='salmonella_consensus',
                 url='https://s3-eu-west-1.amazonaws.com/kepavi/models/salmonella_consensus.xml')
    b.save()
    logging.info('Done !')


@manager.command
def dropdb():
    """Deletes the database"""
    db.drop_all()


def insert_model(xml_model):
    import cobra.io
    import json
    from lxml import etree

    sbml_model = cobra.io.read_sbml_model(xml_model)
    cobra.io.save_json_model(sbml_model, 'test.json')
    d = json.loads(open('test.json').read().encode('utf-8'))

    tree = etree.parse(xml_model)
    root = tree.getroot()
    organism = root[0].attrib['name'].split(' - ')[1]
    biomodel = BiomodelMongo(organism=organism, model=d)
    biomodel.save()


@manager.command
def insert_models():
    import glob
    import cobra.io
    models = glob.glob('./BioModels_Database/*')[14:]
    print models
    for m in models:
        try:
            insert_model(m)
        except Exception:
            pass
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager.run()
