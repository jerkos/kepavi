import logging
import cobra
import requests
import tempfile
import os


def get_sbml_from_s3(url):
    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    name = 'sbml.xml'
    with open('sbml.xml', 'w') as f:
        f.write(resp.text)
    sbml_model = cobra.io.read_sbml_model(name)
    os.remove(name)
    return sbml_model


def _launch_fba(model, objectives, user_params, optimize_sense='maximize'):
    """
    Will flux balance analysis calling `model.optimize`
    Got unicode instead of string

    :param model: cobrapy model
    :param objectives: reactions list representing objectives function
    :param user_params: list of dict reactions bounds that has been changed by user
    :return: solution object

    """

    def get_reac_by_name(name):
        reacts = model.reactions.query(name, 'name')
        try:
            return reacts[0]
        except IndexError:
            logging.warn('reaction not found')
            return None

    for obj in objectives:
        react = get_reac_by_name(str(obj))
        if react is not None:
            react.objective_coefficient = 1.0

    for params in user_params:
        react = get_reac_by_name(str(params['name']))
        if react is not None:
            # Updating bounds
            react.lower_bound = params['lower_bound']
            react.upper_bound = params['upper_bound']

    # start computing a solution
    solution = model.optimize(objective_sense=optimize_sense)
    return solution


