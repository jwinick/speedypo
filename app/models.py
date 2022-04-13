from datetime import datetime
from hashlib import md5
from time import time
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from app import login
import sys
import pymysql



class User(UserMixin):

    def __init__(self, user_id,active=True):
        self.id = user_id
        self.active = active

    def is_active(self):
        return self.active

    def get_id(self):
        return self.id

    # def is_anonymous(self):
    #     return False

    # def is_authenticated(self):
    #     return True

    def get_id(self):
        return self.id

    # def set_password(self, password):
    #     self.password_hash = generate_password_hash(password)

    # def check_password(self, password):
    #     return check_password_hash(self.password_hash, password)

@login.user_loader
def load_user(user_id, remember=True):
    try:
        return User(user_id,True)
    except:
        return None

