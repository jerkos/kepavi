import logging

from mongoengine import StringField, DynamicDocument, DictField
import cobra.io


class BiomodelMongo(DynamicDocument):
    """This a dynamic document: field could change especially `username`
    would be None if the biomodel is public else user's username.
    """

    name = StringField()
    organism = StringField()  # will store 3 letters code from Kegg

    cobra_model = DictField()

    # username = StringField()


