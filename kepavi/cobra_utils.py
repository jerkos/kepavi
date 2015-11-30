import logging
import cobra
from kepavi.kegg_utils import Kegg
import requests
import os
from collections import defaultdict
import random
from kepavi.user.models import KeggReaction

# Sigma js has my preference since it can handle
# larger graph
GRAPH_LIBRARY_BACKEND = {'cytoscape', 'sigma'}

# this metabolites are involved in too much reactions
# and make the visualization too complicated
UNDESIRABLES = {'H',
                'H+',
                'H(+)',
                'NH4(+)',
                'NADH(2-)',
                'NAD(+)',
                'NADP(+)',
                'NADPH',
                'diphosphate(3-)',
                'CO(2)',
                'holo-[acyl-carrier\nprotein]',
                'HOLO-[ACYL-CARRIER\nPROTEIN]',
                'Cl(-)',
                'Fe(2+)',
                'IDP',  # known has intrinsically disordred protein
                # 'acetyl-CoA(4-)',
                'CoA',
                'GTP',
                'UTP(3-)',
                'CTP(3-)',
                'dioxygen',
                'AMP',
                'H2O',
                'ADP',
                'ATP',
                'Diphosphate',
                'Phosphate',
                'phosphate',
                'UDP',
                'Coenzyme-A',
                'Nicotinamide-adenine-dinucleotide',
                'Nicotinamide-adenine-dinucleotide-phosphate',
                'Nicotinamide-adenine-dinucleotide--reduced',
                'Ammonium',
                'CO2'}


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
              flux,
              position,
              bg_color,
              shape='ellipse',
              show_compound_img=False):
    """
    css properties are not applied when they are in snakeCase.
    :param entry:
    :param data: dictionnary containing graph
    :return:

    """

    node_data = {'id': node_id,
                 'label': name[:10] + '...',
                 'full_name': name,
                 'size': 5,
                 'x': position.x if position is not None else random.random(),
                 'y': position.y if position is not None else random.random(),
                 'flux': flux,
                 'cumflux': abs(flux)  # temporary variable
                 }

    data['nodes'].append(node_data)


def _add_edge(data,
              reaction,
              edge_id,
              id1,
              id2,
              flux,
              kegg_reac_id='',
              arrow_src=False,
              arrow_target=True):
    """
    add an edge
    """
    if flux < 0:
        sign = 'neg'
    elif flux > 0:
        sign = 'pos'
    else:
        sign = 'zero'

    edge_data = {'id': edge_id,
                 'label': kegg_reac_id,  # edge_id,
                 'source': id1,
                 'target': id2,
                 'size': 1,
                 # 'type': 'tapered',
                 'flux': flux,
                 'absflux': abs(flux),
                 'reversible': reaction.reversibility if reaction is not None else False,
                 'sign': sign
                 }
    data['edges'].append(edge_data)


def _get_react_name_by_kegg_react_id(react_id):
    if not react_id.startswith('rn:'):
        react_id = 'rn:' + react_id
    try:
        name, equ = KeggReaction.infos_by_id()[react_id]
        return name
    except KeyError:
        return react_id + ' (can not map kegg id)'


def _build_genome_scale_network(model, results):
    """
    render all metabolites (nodes) and reactions (edges)
    of the supplied SBML model

    Could be simplified to iterate on reactions only once
    avoiding creating `flux_by_metabolites_id` variable
    Just wanted to see if this is working or not
    """

    data = {'nodes': [], 'edges': []}

    x_dict = results['x_dict']

    metabolites_ids, edge_ids = set(), set()

    fluxes_by_metabolites_ids = defaultdict(int)

    for r in model.reactions:
        f_reactants, f_products = r.reactants, r.products

        reactants = set(f_reactants) - set([m for m in f_reactants
                                            if m.name in UNDESIRABLES])
        products = set(f_products) - set([m for m in f_products
                                          if m.name in UNDESIRABLES])

        reactants = set([m for m in reactants if not m.name.startswith('NAD')])

        flux = x_dict[r.id]
        target_to_source = flux <= 0

        for _, reactant in enumerate(reactants):
            if reactant.id not in metabolites_ids:
                _add_node(data,
                          reactant.id,
                          'metabolite',
                          reactant.name,
                          flux,
                          None,
                          '#FFFFFF')
                fluxes_by_metabolites_ids[reactant.id] += abs(flux)
                metabolites_ids.add(reactant.id)
            for __, product in enumerate(products):
                if product.id not in metabolites_ids:
                    _add_node(data,
                              product.id,
                              'metabolite',
                              product.name,
                              flux,
                              None,
                              '#FFFFFF')
                    fluxes_by_metabolites_ids[product.id] += abs(flux)
                    metabolites_ids.add(product.id)

                # create an edge id
                edge_id = '-'.join([str(reactant.id),
                                    str(product.id), str(_), str(__)])
                if edge_id not in edge_ids:
                    _add_edge(data,
                              r,
                              edge_id,
                              reactant.id if not target_to_source else product.id,
                              product.id if not target_to_source else reactant.id,
                              flux)
                    edge_ids.add(edge_id)

    # count total flux for each nodes
    nodes = data['nodes']
    for n in nodes:
        n_id = n['id']
        n['cumflux'] = int(fluxes_by_metabolites_ids[n_id])
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

    def get_kegg_id(element):
        if "KEGG" in element.notes:
            kegg_notes = element.notes["KEGG"][0].replace(" ", "").split(',')
            kegg_ids = set(kegg_notes).difference({'0', 'NA'})
            return kegg_ids  # if kegg_id not in ('0', 'NA') else ''
        elif 'kegg.compound' in element.annotation:
            kegg_id = element.annotation['kegg_compound']
            return kegg_id if kegg_id not in ('0', 'NA') else ''
        return ''

    def add_node_if_not_drawn(element_set, element, flux):
        if element.id not in element_set:
            n = element.name[4:]
            name = met_name_by_kegg_id[n] if n in met_name_by_kegg_id else None
            Kegg._add_node(data,
                           element,
                           int(flux),
                           name=name,
                           show_compound_img=None)
            element_set.add(element.id)

    def is_real_reaction(react):
        return pathway.entries[react.id].type != 'ortholog'

    reac_id_by_kegg_id = {}

    for reac in sbml_model.reactions:
        reac_kegg_ids = get_kegg_id(reac)
        for reac_kegg_id in reac_kegg_ids:
            reac_id_by_kegg_id[reac_kegg_id] = reac.id

    met_name_by_kegg_id = {}
    for met in sbml_model.metabolites:
        met_kegg_ids = get_kegg_id(met)
        for met_kegg_id in met_kegg_ids:
            met_name_by_kegg_id[met_kegg_id] = met.name

    data = {'nodes': [], 'edges': []}

    metabolites_id = set()
    fluxes_by_metabolites_ids = defaultdict(int)

    for reaction in pathway.reactions:
        if not is_real_reaction(reaction):
            continue

        # skip rn: from the beginning, correspond to the kegg_id of the reaction
        full_reac_name = reaction.name.split()[0]
        reac_name = full_reac_name[3:]  # if reaction.name.startswith('rn:') else reaction.name

        reac_label = _get_react_name_by_kegg_react_id(full_reac_name)

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

        sbml_reaction = None
        if matching_reaction is not None:
            sbml_reaction = sbml_model.reactions.get_by_id(matching_reaction)

        for _, reactant in enumerate(reaction.substrates):
            if reactant.name in UNDESIRABLES:
                continue
            # add not if does not exist yet
            fluxes_by_metabolites_ids[reactant.id] += abs(flux)
            add_node_if_not_drawn(metabolites_id, reactant, flux)

            # reac_id = id_by_name[reactant.name]  # if reactant.id
            for __, product in enumerate(reaction.products):
                if product.name in UNDESIRABLES:
                    continue
                fluxes_by_metabolites_ids[product.id] += abs(flux)
                add_node_if_not_drawn(metabolites_id, product, flux)

                # product_id = id_by_name[product.name]  # product.id
                arrow_src = reaction.type == 'reversible'
                edge_id = '-'.join([str(reactant.id),
                                    str(product.id), str(_), str(__)])

                _add_edge(data,
                          sbml_reaction,
                          edge_id,
                          reactant.id,
                          product.id,
                          flux,
                          kegg_reac_id=reac_label,
                          arrow_src=arrow_src)

    # count total flux for each nodes
    nodes = data['nodes']
    for n in nodes:
        n_id = n['id']
        n['cumflux'] = int(fluxes_by_metabolites_ids[n_id])
    print data
    return data


def build_cobra_network(sbml_model, results):
    """
    graph based on the sbml model only, i.e. all the
    reactions containing products and reactants

    :param sbml_model:
    :param results:
    :return:
    """

    data = {'nodes': [], 'edges': []}

    added_node = set()

    id_by_name = {}

    def add_node(elements):
        for e in elements:
            e_name = e.name
            if e_name in UNDESIRABLES:
                continue
            e_id = e.id
            if e_name not in added_node:
                added_node.add(e_name)
                id_by_name[e_name] = e_id
                Kegg._add_node(data,
                               e_id,
                               'metabolites',
                               e.name, None,
                               '#000000')

    for reaction in sbml_model.reactions:
        add_node(reaction.reactants)
        add_node(reaction.products)
        for reactant in reaction.reactants:
            if reactant.name in UNDESIRABLES:
                continue
            reac_id = id_by_name[reactant.name]  # if reactant.id
            for product in reaction.products:
                if product.name in UNDESIRABLES:
                    continue
                product_id = id_by_name[product.name]  # product.id
                arrow_src = reaction.reversibility

                _add_edge(data,
                          reaction,
                          reac_id,
                          product_id,
                          results['x_dict'][reaction.id],
                          arrow_src=arrow_src)
    return data
