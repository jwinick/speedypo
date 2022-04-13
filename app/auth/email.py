from flask import render_template, current_app
from app.email import send_email
from app.models import User, load_user
from app.main.routes import get_user
from app.myconnutils import getConnection

def send_password_reset_email(user_id,token):
    user_id = str(user_id)

    connection = getConnection()
    try:
      with connection.cursor() as cursor:
        sql = """SELECT `email`
              ,`username`
              FROM `user`
              WHERE `user_id` = %s
            """
        cursor.execute(sql,(user_id))
        result = cursor.fetchone()
    finally:
      connection.close()

    email = result['email']
    name = result['username']

    send_email('[SpeedyPO] Reset Your Password',
               sender='support@speedypo.com',
               recipients=[email],
               text_body=render_template('email/reset_password.txt',
                                         user_name=name, token=token),
               html_body=render_template('email/reset_password.html',
                                         user_name=name, token=token))


def send_confirm_register_email(user_id,token):
    user_id = str(user_id)

    connection = getConnection()
    try:
      with connection.cursor() as cursor:
        sql = """SELECT `email`
              ,`username`
              FROM `user`
              WHERE `user_id` = %s
            """
        cursor.execute(sql,(user_id))
        result = cursor.fetchone()
    finally:
      connection.close()

    email = result['email']
    name = result['username']

    send_email('[SpeedyPO] Confirm Your Registeration',
                 sender='support@speedypo.com',
                 recipients=[email],
                 text_body=render_template('email/confirm_register.txt',
                                           user_name=name, token=token),
                 html_body=render_template('email/confirm_register.html',
                                           user_name=name, token=token))
    return 'Great success'
