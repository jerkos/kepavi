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

    logging.info('Getting kegg organism list...')
    kegg_list = Kegg.get_org_list()

    # use only get memory error otherwise
    # print BiomodelMongo.objects.only('organism', 'name').all()
    mongo_list = dict((b.organism, b.name) for b in BiomodelMongo.objects.only('organism', 'name').all())

    mongo_orgs = set(mongo_list.keys())

    # to prevent insertion porting the same name
    kegg_names = set()

    logging.info('Insertion begins...')
    d = csv.DictReader(kegg_list.split('\n'), delimiter='\t', fieldnames=('code', 'org', 'tax'))
    for row in d:
        code, org, tax = row['code'], row['org'], row['tax']
        if org in mongo_orgs:
            if tax not in kegg_names:
                o = Organism(row['code'], row['org'], row['tax'])
                o.save()
                b = Biomodel(name=tax, kegg_org=org)
                b.save()
                # finally tax to the set
                kegg_names.add(tax)

    # insert user
    u = User(username='marco',email='cram@hotmail.fr', password='Marco@1986')
    u.save()

    logging.info('Done !')


@manager.command
def dropdb():
    """Deletes the database"""
    db.drop_all()


def insert_model(xml_model):
    import cobra.io
    import json

    sbml_model = cobra.io.read_sbml_model(xml_model)
    # cobra.io.save_json_model(sbml_model, 'test.json')
    # d = json.loads(open('test.json').read().encode('utf-8'))
    d = cobra.io._to_dict(sbml_model)
    infos = retrieve_kegg_org_id(xml_model)
    if infos is None:
        logging.warn('No infos found')
        return False

    kegg_org_id, model_name = infos['kegg_org_id'], infos['model_name']
    if kegg_org_id is None or model_name is None:
        return False

    biomodel = BiomodelMongo(name=model_name, organism=kegg_org_id, cobra_model=d)
    biomodel.save()
    return True


def retrieve_kegg_org_id(xml_model):
    from lxml import etree
    tree = etree.parse(xml_model)
    root = tree.getroot()

    main_ns = root.nsmap[None]
    model = root.xpath('x:model',  namespaces={'x': main_ns})[0]
    model_name = model.attrib['name'].split(' - ')[-1]
    annots = root.xpath('x:model/x:annotation', namespaces={'x': main_ns})
    if not annots:
        return None
    annot = annots[0]

    rdf = None
    for c in annot.getchildren():
        if c.tag.split('}')[-1] == 'RDF':  # i still do not have acces to ref namespace
            rdf = c
            break
    namespaces = rdf.nsmap
    l = rdf.xpath('x:Description/y:isDerivedFrom/x:Bag/x:li', namespaces={'x': namespaces['rdf'],
                                                                          'y': namespaces['bqmodel']})
    if not l:
        return None
    is_derived = l[0]
    resource = is_derived.attrib["".join(['{', namespaces['rdf'], '}', 'resource'])]
    if '/' not in resource:
        return None
    kegg_org_id = resource.split('/')[-1]
    return {'kegg_org_id': kegg_org_id, 'model_name': model_name}


@manager.command
def insert_models():
    import glob
    models = glob.glob('./BioModels_Database/*')
    i, l = 0.0, float(len(models))
    success = 0.0
    for m in models:
        try:
            if insert_model(m):
                success += 1
        except Exception as e:
            logging.error(e.message)

        i += 1
        if i > 0:
            logging.info("complete: {}%, success: {}%".format(round((i / l) * 100), round((success/i) * 100)))


@manager.command
def test_read_models():
    m = BiomodelMongo.objects(organism='sse').first()
    import cobra.io, json
    try:
        s = json.dumps(m.model).encode('utf-8')
        with open('test.json', 'w') as f:
            f.write(s)

        sbml_model = cobra.io.load_json_model('test.json')
        # sbml_model = cobra.io._from_dict(m.model)
    except Exception as e:
        print "Got an exception:", e
        return None
    print "NOTES:", sbml_model.reactions[0].notes
    return sbml_model


@manager.command
def test_unique_kegg_names():
    kegg_list = Kegg.get_org_list()
    from collections import Counter
    l = []
    d = csv.DictReader(kegg_list.split('\n'), delimiter='\t', fieldnames=('code', 'org', 'tax'))
    for row in d:
        code, org, tax = row['code'], row['org'], row['tax']
        l.append(tax)
    c = Counter(l)
    max_val = max(c.values())
    print "Max val:", max_val
    while max_val > 1:
        print "#", max_val, " count:", len([v for v in c.values() if v == max_val])
        max_val -= 1

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager.run()
