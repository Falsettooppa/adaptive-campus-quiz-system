from flask import current_app, g
from pymongo import MongoClient


def get_db():
    if "mongo_client" not in g:
        g.mongo_client = MongoClient(current_app.config["MONGO_URI"])
        g.db = g.mongo_client[current_app.config["DATABASE_NAME"]]
    return g.db


def close_db(e=None):
    mongo_client = g.pop("mongo_client", None)
    g.pop("db", None)

    if mongo_client is not None:
        mongo_client.close()