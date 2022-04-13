import os
from dotenv import load_dotenv
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

test_location = str(Path(__file__).resolve().parents[3])

if(test_location == '/Users/jacobwinick'):
    class Config(object):
        SECRET_KEY = '**********'
        UPLOAD_FOLDER = '/app/uploads'
        db_user = '**********'
        db_password = '**********'
        db_host = '**********'
        db_port = 3306
        db_name = 'db'
        MAIL_SERVER = 'smtp.gmail.com'
        MAIL_PORT = 465
        MAIL_USE_TLS = False
        MAIL_USE_SSL = True
        MAIL_USERNAME = '**********'
        MAIL_PASSWORD = '**********'

        POSTS_PER_PAGE = 25
        GRAVATAR_SIZE = 70
        GRAVATAR_RATING = 'g'
        SEND_FILE_MAX_AGE_DEFAULT = 0
        GRAVATAR_DEFAULT = 'retro'
else:
    class Config(object):
        SECRET_KEY = '**********'
        UPLOAD_FOLDER = '/app/uploads'
        db_user = '**********'
        db_password = '**********'
        db_host = 'localhost'
        db_name = 'db'
        MAIL_SERVER = 'smtp.gmail.com'
        MAIL_PORT = 465
        MAIL_USE_TLS = False
        MAIL_USE_SSL = True
        MAIL_USERNAME = '**********'
        MAIL_PASSWORD = '**********'
        SEND_FILE_MAX_AGE_DEFAULT = 0
        # ADMINS = ['jlwinick@gmail.com']
        POSTS_PER_PAGE = 25
        GRAVATAR_SIZE = 70
        GRAVATAR_RATING = 'g'
        GRAVATAR_DEFAULT = 'retro'

