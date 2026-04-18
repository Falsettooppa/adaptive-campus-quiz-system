from flask import Flask
from config import Config
from app.db import close_db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from app.routes import main
    from app.auth import auth

    app.register_blueprint(main)
    app.register_blueprint(auth)

    app.teardown_appcontext(close_db)

    return app