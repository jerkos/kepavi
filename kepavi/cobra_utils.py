import logging
import cobra
from kepavi.kegg_utils import Kegg
import requests
import tempfile
import os
from itertools import groupby
from collections import defaultdict
import random

# Sigma js has my preference since it can handle
# larger graph
GRAPH_LIBRARY_BACKEND = {'cytoscape', 'sigma'}


def get_sbml_from_s3(url):
    """
    load model stored in AWS S3 service using requests
    library.
    :param url: url to fetch
    :return: cobra model object could be None
    """

    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    name = 'sbml.xml'
    # with tempfile.NamedTemporaryFile(delete=False) as f:
    with open(name, 'w') as f:
        f.write(resp.text.encode('utf-8'))

    sbml_model = None
    try:
        sbml_model = cobra.io.read_sbml_model(name)
    except Exception:
        pass

    # remove file
    os.remove(name)

    return sbml_model


def _launch_fba(model, objectives, user_params, optimize_sense='maximize'):
    """
    Will flux balance analysis calling `model.optimize`
    Got unicode instead of string

    :param model: cobrapy model
    :param objectives: reactions list representing objectives function
    :param user_params: list of dict reactions bounds that has been changed 
                        by user
    :return: solution object

    """

    def get_reac_by_name(name):

        reacts = model.reactions.query(lambda x: True if x == name else False, 'name')
        try:
            return reacts[0]
        except IndexError:
            logging.warn('reaction not found: {}'.format(name))
            return None
    # end function

    # update objective functions
    for obj in objectives:
        react = get_reac_by_name(str(obj['name']))
        if react is not None:
            react.objective_coefficient = 1.0

    # update constraints
    for params in user_params:
        react = get_reac_by_name(str(params['name']))
        if react is not None:
            # Updating bounds
            react.lower_bound = params['lower_bound']
            react.upper_bound = params['upper_bound']

    # start computing a solution
    solution = model.optimize(objective_sense=optimize_sense)
    return solution


def _add_node(data,
              node_id,
              klass,
              name,
              position,
              bg_color,
              shape='ellipse',
              show_compound_img=False, 
              backend='sigma'):
    
    """
    css properties are not applied when they are in snakeCase.
    :param entry:
    :param data: dictionnary containing graph
    :return:

    """

    if backend not in GRAPH_LIBRARY_BACKEND:
        raise NameError('backend library not in {cytoscape, sigma}')

    node_data = {'id': node_id,
                 #'name': name,
                 'label': name,
                 'size': 5,
                 'x': position.x if position is not None else random.random(),
                 'y': position.y if position is not None else random.random()
                 #'content': name,
                 #'textValign': 'top',
                 #'width': 10,
                 #'height': 10,
                 #'backgroundColor': bg_color,
                 #'type': shape,
                 #'borderColor': '#000000',
                 #'borderWidth': 4
                 }

    # if backend == 'sigma':
    #     node_data.update(
    #         {
    #             'x': position.x if position is not None else random.random(),
    #             'y': position.y if position is not None else random.random()
    #         }
    #     )

    if backend == 'sigma':
        data['nodes'].append(node_data)
    else:
        data['nodes'].append(
            {
                'data': node_data,
                'position':
                    {'x': position[0],
                     'y': position[1]},
                'grabbable': True,
                'selectable': True,
                'classes': klass
            }
        )


def _add_edge(data, reaction, id1, id2, flux, arrow_src=False, arrow_target=True, backend='sigma'):
    concat = '-'.join([str(id1), str(id2)])
    edge_data = {'id': reaction.id if reaction is not None else concat,
                 #'content': reaction.name if reaction is not None else 'NA',
                 'source': id1,
                 'target': id2,
                 'size': 1,
                 'type': 'curvedArrow',
                 'data': 
                    {
                        'flux': flux,
                        'reversible': reaction.reversibility
                    }
                 #'color': '#ccc'
                 #'targetArrowShape':  'triangle' if arrow_target else 'none',
                 #'sourceArrowShape':  'triangle' if arrow_src else 'none',
                 #'flux': flux,
                 #'absflux': abs(flux)
                }
    if backend == 'cytoscape':
        data['edges'].append(
            {
                'data': edge_data
            }
        )
    else:
        data['edges'].append(edge_data)


def _build_genome_scale_network(model, results):
    data = {'nodes': [], 'edges': []}

    x_dict = results['x_dict']

    metabolites_ids = set()
    for m in model.metabolites:
        if m.name in {'H',
                      'H+',
                      'H(+)',
                      'H2O',
                      'ADP',
                      'ATP',
                      'Diphosphate',
                      'Phosphate',
                      'UDP',
                      'Coenzyme-A',
                      'Nicotinamide-adenine-dinucleotide',
                      'Nicotinamide-adenine-dinucleotide-phosphate',
                      'Nicotinamide-adenine-dinucleotide--reduced',
                      'Ammonium',
                      'CO2'} or m.compartment == 'e':
            continue
        # data, node_id, name, position, bg_color, shape='ellipse', show_compound_img=False
        # data, node_id, klass, name, position, bg_color, shape='ellipse', show_compound_img=False
        _add_node(data, m.id, 'metabolite', m.name, None, '#FFFFFF')
        metabolites_ids.add(m.id)
    for r in model.reactions:
        if r.reactants and r.products:
            if r.reactants[0].id in metabolites_ids and r.products[0].id in metabolites_ids: 
                _add_edge(data, r, r.reactants[0].id, r.products[0].id, x_dict[r.id])
    return data


def find_reactions(reactants_kegg_id, products_kegg_id, kegg_ids_by_reac_id):
    matches = defaultdict(list)
    for reaction_id, (reac_kegg_ids, prod_kegg_ids) in kegg_ids_by_reac_id.iteritems():
        reac_intersect = reactants_kegg_id.intersection(reac_kegg_ids)
        prod_intersect = products_kegg_id.intersection(prod_kegg_ids)
        if reac_intersect and prod_intersect:
            matches[len(reac_intersect) + len(prod_intersect)].append(reaction_id)
    if not matches:
        return frozenset({})
    max_match = max(matches.keys())
    return frozenset(matches[max_match])


def build_kegg_network_mixed(pathway,
                             kegg_model_name,
                             sbml_model,
                             results):
    """
    Build network using sbml_model, kegg model and results
    We use the kegg_model to get the layout
    Basically, this will be used when the user requests a graph
    of a specific pathway.

    """

    not_wanted = ('H', 'H2O', 'ADP', 'ATP', 'Diphosphate',
                  'Phosphate', 'UDP', 'Coenzyme-A', 'AMP', 'Dihydroxyacetone',
                  'Dihydroxyacetone-phosphate', 'Nicotinamide-adenine-dinucleotide',
                  'Acetyl-CoA', 'Nicotinamide-adenine-dinucleotide-phosphate',
                  'Nicotinamide-adenine-dinucleotide--reduced',
                  'Ammonium', 'CO2')

    def get_kegg_id(element):
        if "KEGG" in element.notes:
            kegg_notes = element.notes["KEGG"][0].replace(" ", "").split(',')
            kegg_ids = set(kegg_notes).difference({'0', 'NA'})
            return kegg_ids  # if kegg_id not in ('0', 'NA') else ''
        elif 'kegg.compound' in element.annotation:
            kegg_id = element.annotation['kegg_compound']
            return kegg_id if kegg_id not in ('0', 'NA') else ''
        return ''
        # raise ValueError('No KEGG ids found...')

    def add_to_set(element_set, elements):
        for m in elements:
            kegg_id = get_kegg_id(m)
            if kegg_id:
                element_set.add(kegg_id)

    def is_real_reaction(react):
        # try:
        if pathway.entries[react.id].type == 'ortholog':
            return False
        return True
        # except KeyError:
        #    return False

    reac_id_by_kegg_id = {}
    i = 0
    for reac in sbml_model.reactions:
        reac_kegg_ids = get_kegg_id(reac)
        for reac_kegg_id in reac_kegg_ids:
            reac_id_by_kegg_id[reac_kegg_id] = reac.id

    met_name_by_kegg_id = {}
    for met in sbml_model.metabolites:
        met_kegg_ids = get_kegg_id(met)
        for met_kegg_id in met_kegg_ids:
            met_name_by_kegg_id[met_kegg_id] = met.name

            # reactants_set, products_set = set(), set()
            # add_to_set(reactants_set, reac.reactants)
            # add_to_set(products_set, reac.products)
            # reac_id_by_kegg_id[reac.id] = (reactants_set, products_set)

    data = {'nodes': [], 'edges': []}

    for entry_id, entry in pathway.entries.iteritems():
        entry_type = entry.type
        # if we only focus on the metabolic network, we remove
        # map and ortholog entries since it is getting more
        # obfuscated with it.
        if entry_type != 'compound':  # in {'gene', 'ortholog', 'map', 'enzyme', 'group'}:
            continue

        n = entry.name[4:] # entry.name
        name = met_name_by_kegg_id[n] if n in met_name_by_kegg_id else None
        Kegg._add_node(data, entry, name=name, show_compound_img=None)

    min_flux, max_flux = 1000, -1000

    for reaction in pathway.reactions:
        if not is_real_reaction(reaction):
            continue

        # skip rn: from the beginning, correspond to the kegg_id of the reaction
        reac_name = reaction.name.split()[0][3:]  # if reaction.name.startswith('rn:') else reaction.name

        # substrate_kegg_ids = {substrate.name[4:] for substrate in reaction.substrates}
        # product_kegg_ids = {product.name[4:] for product in reaction.products}

        matching_reaction = None
        if reac_name in reac_id_by_kegg_id:
            matching_reaction = reac_id_by_kegg_id[reac_name]
        else:
            logging.warn("no matching sbml reaction for reaction kegg ID: {}".format(reac_name))

        # matching_reactions = find_reactions(substrate_kegg_ids, product_kegg_ids, reac_id_by_kegg_id)
        # flux = results['x_dict'][list(matching_reactions)[0]] if len(matching_reactions) == 1 else 0

        flux = results['x_dict'][matching_reaction] if matching_reaction is not None else 0

        if flux < min_flux:
            min_flux = flux
        if flux > max_flux:
            max_flux = flux
        # for substrate in reaction.substrates:
        #     substrate_id = substrate.id
        #     if reaction.type == 'reversible':
        #         _add_edge(data, substrate_id, reac_id, flux, arrow_src=True, arrow_target=False)
        #     else:
        #         _add_edge(data, substrate_id, reac_id, flux, arrow_src=False, arrow_target=False)
        #
        # for product in reaction.products:
        #     _add_edge(data, reac_id, product.id, flux, arrow_src=False, arrow_target=True)

        sbml_reaction = sbml_model.reactions.get_by_id(matching_reaction) if matching_reaction is not None else None

        for reactant in reaction.substrates:
            if reactant.name in not_wanted:
                continue
            # reac_id = id_by_name[reactant.name]  # if reactant.id
            for product in reaction.products:
                if product.name in not_wanted:
                    continue
                # product_id = id_by_name[product.name]  # product.id
                arrow_src = reaction.type == 'reversible'

                _add_edge(data,
                          sbml_reaction,
                          reactant.id,
                          product.id,
                          flux, arrow_src=arrow_src)

        data['flux_min'] = min_flux
        data['flux_max'] = max_flux

    return data


def build_cobra_network(sbml_model, results):
    """
    graph based on the sbml model only, i.e. all the
    reactions containing products and reactants

    :param sbml_model:
    :param results:
    :return:
    """

    not_wanted = ('H', 'H2O', 'ADP', 'ATP', 'Diphosphate', 'Phosphate',
                  'UDP', 'Coenzyme-A', 'AMP', 'Dihydroxyacetone',
                  'Dihydroxyacetone-phosphate',
                  'Nicotinamide-adenine-dinucleotide',
                  'Acetyl-CoA', 'Nicotinamide-adenine-dinucleotide-phosphate',
                  'Nicotinamide-adenine-dinucleotide--reduced',
                  'Ammonium', 'CO2')

    fluxes = [results['x_dict'][_.id] for _ in sbml_model.reactions]
    flux_min, flux_max = min(fluxes), max(fluxes)
    data = {'nodes': [], 'edges': []}

    added_node = set()

    id_by_name = {}

    def add_node(elements):
        for e in elements:
            e_name = e.name
            if e_name in not_wanted:
                continue
            e_id = e.id
            if e_name not in added_node:
                added_node.add(e_name)
                id_by_name[e_name] = e_id
                Kegg._add_node(data, e_id, 'metabolites', e.name, None, '#000000')

    for reaction in sbml_model.reactions:
        add_node(reaction.reactants)
        add_node(reaction.products)
        for reactant in reaction.reactants:
            if reactant.name in not_wanted:
                continue
            reac_id = id_by_name[reactant.name]  # if reactant.id
            for product in reaction.products:
                if product.name in not_wanted:
                    continue
                product_id = id_by_name[product.name]  # product.id
                arrow_src = reaction.reversibility

                _add_edge(data, reaction, reac_id, product_id, results['x_dict'][reaction.id], arrow_src=arrow_src)
    return data



