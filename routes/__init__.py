from routes.auth_routes import auth_bp
from routes.camera_routes import camera_bp


def init_app(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(camera_bp)
