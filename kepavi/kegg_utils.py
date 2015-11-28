# -*- coding: utf-8 -*-

import csv
import sqlite3

from Bio.KEGG.KGML.KGML_parser import read as kgml_read
from Bio.KEGG.KGML.KGML_pathway import Entry, Component, Reaction, Relation

from kepavi.extensions import db
import requests


class Organism(db.Model):
    """
    Organism defines in Kegg organism database
    scrapped using get requests using REST Api

    """

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

    @staticmethod
    def get_org_list():
        """
        return all organism listed in Kegg database
        """

        resp = requests.get(''.join([Kegg.BASE_URL, 'list/organism']))
        return resp.text

    @staticmethod
    def get_pathways_list(org='hsa'):
        """
        return all pathway for an organism listed in Kegg
        database
        :param org organism shortcode in Kegg database
        """

        resp = requests.get(''.join([Kegg.BASE_URL, 'list/pathway/', org]))
        if resp.status_code == 200:
            d = csv.DictReader(resp.text.split('\n'),
                               delimiter='\t',
                               fieldnames=('id', 'name'))
            return [row for row in d]
        return {}

    @staticmethod
    def get_kgml_obj(pathway_id):
        """
        return Kegg KGML_pathway object
        :param pathway_id pathway id in the kegg database
               could be None if request failed
        """

        if pathway_id.startswith('path:'):
            pathway_id = pathway_id.replace('path:', '')
        resp = requests.get(''.join([Kegg.BASE_URL,
                                     'get/',
                                     pathway_id,
                                     '/kgml']))
        if resp.status_code == 200:
            return kgml_read(resp.text)
        return None

    @staticmethod
    def _add_node(data, entry, flux, name=None, show_compound_img=False):
        """
        css properties are not applied when they are in snakeCase.
        :param entry:
        :param data: dictionnary containing graph
        :return:
        """

        entry_type = entry.type
        graphics = entry.graphics[0]

        node_name = name or graphics.name

        node_data = {'id': entry.id,
                     'name': node_name[:10] + '...',
                     'full_name': node_name,
                     'label': node_name,
                     'content': node_name,
                     'size': 5,
                     'x': graphics.x,
                     'y': graphics.y,
                     'flux': flux,
                     'cumflux': abs(flux)}

        # not applicable yet
        if entry_type == 'compound' and show_compound_img:
            node_data.update({
                'type': 'rectangle',
                'backgroundImage': ''.join([Kegg.BASE_URL, 'get/',
                                            entry.name[4:], '/image']),
                'borderWidth': 0,

            })

        data['nodes'].append(node_data)

    # does not seem to be used anymore
    @staticmethod
    def _add_edge(data, id1, id2, arrow_src=False, arrow_target=True):
        concat = '-'.join([str(id1), str(id2)])
        edge_data = {'id': concat,
                     'label': concat,
                     'source': id1,
                     'target': id2,
                     'targetArrowShape': 'triangle' if arrow_target else 'none',
                     'sourceArrowShape': 'triangle' if arrow_src else 'none'
                     }

        data['edges'].append(edge_data)


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
