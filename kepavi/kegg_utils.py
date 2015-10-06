# -*- coding: utf-8 -*-

import csv
import sqlite3

from Bio.KEGG.KGML.KGML_parser import read as kgml_read
from Bio.KEGG.KGML.KGML_pathway import Entry, Component, Reaction, Relation
from flask import jsonify

from kepavi.extensions import db
import requests


class Organism(db.Model):
    __tablename__ = "organism"

    code = db.Column(db.String(15), primary_key=True)
    org = db.Column(db.String(15), nullable=False)
    tax = db.Column(db.Text())

    def __init__(self, *args):
        self.code, self.org, self.tax = args

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self


class Kegg(object):
    BASE_URL = 'http://rest.kegg.jp/'

    ENTRY_COLOR = {}
    HMDB = 'kepavi/ressources/hmdb.sqlite'

    CYTOSCAPE_SHAPES = {'rectangle': 'rectangle',
                        'roundrectangle': 'roundrectangle',
                        'circle': 'ellipse'}
                        # 'triangle',
                        # 'pentagon',
                        # 'hexagon',
                        # 'heptagon',
                        # 'octagon',
                        # 'star',
                        # 'diamond',
                        # 'vee',
                        # 'rhomboid'}

    @staticmethod
    def get_org_list():
        resp = requests.get(''.join([Kegg.BASE_URL, 'list/organism']))
        return resp.text

    @staticmethod
    def get_pathways_list(org='hsa'):
        resp = requests.get(''.join([Kegg.BASE_URL, 'list/pathway/', org]))
        if resp.status_code == 200:
            d = csv.DictReader(resp.text.split('\n'), delimiter='\t', fieldnames=('id', 'name'))
            return [row for row in d]
        return {}

    @staticmethod
    def get_kgml(pathway_id):
        if pathway_id.startswith('path:'):
            pathway_id = pathway_id.replace('path:', '')
        resp = requests.get(''.join([Kegg.BASE_URL, 'get/', pathway_id, '/kgml']))
        if resp.status_code == 200:
            return kgml_read(resp.text)
        return None

    @staticmethod
    def get_kgml_network(pathway_id, show_compounds_img=False):
        if pathway_id.startswith('path:'):
            pathway_id = pathway_id.replace('path:', '')
        resp = requests.get(''.join([Kegg.BASE_URL, 'get/', pathway_id, '/kgml']))
        if resp.status_code == 200:
            # start building graph

            data = {'nodes': [], 'edges': []}
            pathway = kgml_read(resp.text)

            cpd_names_by_cpd_ids = Kegg._fetch_compounds_name()

            for entry_id, entry in pathway.entries.iteritems():
                entry_type = entry.type
                # if we only focus on the metabolic network, we remove
                # map and ortholog entries since it is getting more
                # obfuscated with it.
                if entry_type in {'ortholog', 'map', 'enzyme', 'group'}:
                    continue
                Kegg._add_node(data, entry)

            for reaction in pathway.reactions:
                reac_id = reaction.id

                for substrate in reaction.substrates:
                    substrate_id = substrate.id
                    if reaction.type == 'reversible':
                        Kegg._add_edge(data, substrate_id, reac_id, arrow_src=True, arrow_target=False)
                    else:
                        Kegg._add_edge(data, substrate_id, reac_id, arrow_src=False, arrow_target=False)
                for product in reaction.products:
                    Kegg._add_edge(data, reac_id, product.id, arrow_src=False, arrow_target=True)

            # for relation in pathway.relations:
            #     if relation.type == 'maplink':
            #         continue
            #     relation_types = {relation.entry1.type, relation.entry2.type}
            #     if 'compound' in relation_types and 'ortholog' in relation_types:
            #         continue
            #     _add_edge(relation.entry1.id, relation.entry2.id)

            return data
        return []

    @staticmethod
    def _add_node(data, entry, name=None, show_compound_img=False):
        """
        css properties are not applied when they are in snakeCase.
        :param entry:
        :param data: dictionnary containing graph
        :return:
        """
        entry_type = entry.type
        graphics = entry.graphics[0]

        # if entry_type == 'gene':
        #     name = entry.reaction.split(' ')[0][3:]
        # elif entry_type == 'compound':
        #     name = graphics.name  # cpd_names_by_cpd_ids.get(graphics.name, graphics.name)
        # else:
        #     name = graphics.name

        node_name = name or graphics.name

        node_data = {'id': entry.id,
                     'name': node_name,
                     'content': node_name,
                     # reactions labeled are centered by default
                     'textValign': 'center' if entry_type == 'gene' else 'top',
                     'width': graphics.width,
                     'height': graphics.height,
                     'backgroundColor': graphics.bgcolor,
                     'type': Kegg.CYTOSCAPE_SHAPES[graphics.type],
                     'borderColor': '#000000',
                     'borderWidth': 1}
                     # 'backgroundImage': 'none',
                     # 'backgroundFit': 'cover',
                     # 'backgroundClip': 'none'}

        if entry_type == 'compound' and show_compound_img:
            node_data.update({
                'type': 'rectangle',
                'backgroundImage': ''.join([Kegg.BASE_URL, 'get/', entry.name[4:], '/image']),
                'borderWidth': 0,
                # 'background-fit': 'cover',
                # 'background-clip': 'none'
            })

        data['nodes'].append(
            {
                'data': node_data,
                'position':
                    {'x': graphics.x,
                     'y': graphics.y},
                # 'locked': True,
                'grabbable': True
            }
        )

    @staticmethod
    def _add_edge(data, id1, id2, arrow_src=False, arrow_target=True):
        concat = '-'.join([str(id1), str(id2)])
        data['edges'].append(
            {
                'data':
                    {'id': concat,
                     'source': id1,
                     'target': id2,
                     'targetArrowShape':  'triangle' if arrow_target else 'none',
                     'sourceArrowShape':  'triangle' if arrow_src else 'none'
                     },
             }
        )

    @staticmethod
    def _fetch_compounds_name(pathway=None):
        con = sqlite3.connect(Kegg.HMDB)
        cursor = con.cursor()
        results = {}

        if pathway is not None:
            compounds_id = [c.name[4:] for c in pathway.compounds]

            for c_id in compounds_id:
                r = cursor.execute('select name from metabolite where kegg_id = (?)', (c_id,)).fetchone()
                if r is None:
                    results[c_id] = r
                else:
                    results[c_id] = r[0]
        else:
            for row in cursor.execute('select name, kegg_id from metabolite').fetchall():
                results[row[1]] = row[0] or None
        return results
