from peewee import *
from playhouse.postgres_ext import PostgresqlExtDatabase
from playhouse.postgres_ext import JSONField
from config import bdname, bduser, bdpassword, bdport, bdhost

db = PostgresqlExtDatabase(bdname, user=bduser, password=bdpassword,
                           host=bdhost, port=bdport)


class Tasks(Model):
    url = TextField(unique=True)
    tag = TextField()
    done = BooleanField(default=False)

    class Meta:
        database = db


class Items(Model):
    url = TextField(unique=True)
    articul = IntegerField(default=0)
    subpart = TextField(default="")
    about = TextField(default="")
    date = TextField(default="")
    is_agency = TextField(default="")
    name = TextField(default="")
    company = TextField(default="")
    saller_login = TextField(default="")
    saller_url = TextField(default="")
    saller_contacts = TextField(default="")
    tag = TextField(default="")
    params = JSONField(default={})
    deleted = BooleanField(default=False)

    class Meta:
        database = db

# db.drop_tables([Items, Tasks])
# db.create_tables([Items, Tasks])
