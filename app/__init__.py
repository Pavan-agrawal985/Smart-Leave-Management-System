from flask import Flask
from config import Config
from app.extensions import db, migrate, csrf, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from app import models  # noqa: F401
    from app.routes import auth, main
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)

    @app.route("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return "Database connected"

    return app