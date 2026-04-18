from pymongo import MongoClient
from flask import current_app, g

def get_db():
    if "db" not in g:
        client = MongoClient(current_app.config["MONGO_URI"])
        g.mongo_client = client
        g.db = client[current_app.config["DATABASE_NAME"]]
    return g.db

def close_db(e=None):
    client = g.pop("mongo_client", None)
    if client is not None:
        client.close()