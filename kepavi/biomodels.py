from mongoengine import StringField, DynamicDocument, DictField


class BiomodelMongo(DynamicDocument):
    organism = StringField()
    strain = StringField(max_length=50)

    model = DictField()


