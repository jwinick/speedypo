import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os
from flask import Flask, request, current_app
from flask_login import LoginManager
#from flask_bootstrap import Bootstrap
#from flask_moment import Moment
#from flask_datepicker import datepicker
from config import Config
#from flask_gravatar import Gravatar
from flask_mail import Mail




login = LoginManager()
login.login_view = "auth.login"
login.login_message = 'Please log in to access this page.'
mail = Mail()
#bootstrap = Bootstrap()
#moment = Moment()
#gravatar = Gravatar()
#datepicker = datepicker()

basedir = os.path.abspath(os.path.dirname(__file__))

#db = create_engine('mysql://localhost/test', strategy='threadlocal')

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    #gravatar.init_app(app)
    #db.init_app(app)
    # migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    #bootstrap.init_app(app)
    #moment.init_app(app)
    #datepicker.init_app(app)

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app


from app import models


