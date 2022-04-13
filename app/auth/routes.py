from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from werkzeug.urls import url_parse
from flask_login import login_user, logout_user, current_user, login_required
from app.auth import bp
from app import login
from app.models import User, load_user
from app.myconnutils import getConnection
import pymysql.cursors
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql.cursors
from time import time
import jwt
import json
from app.auth.email import send_password_reset_email, send_confirm_register_email
import glob
# cursor = connection.cursor()


# @login.user_loader
# def load_user(id,remember=True):
#     try:
#         User(int(id),True)
#     except:
#         return None

def get_user(user_id):
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT * from user WHERE user_id = %s"
            cursor.execute(sql,(user_id))
            result = cursor.fetchone()
            return result
    finally:
        connection.close()


def get_user_from_email(email):
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM `user` u WHERE u.email = %s AND u.created IS NOT NULL ORDER BY u.created DESC LIMIT 1"
            cursor.execute(sql,(str(email)))
            result = cursor.fetchone()
            result = result['user_id']
            return result
    finally:
        connection.close()

@bp.route('/find_email',methods=['POST'])
def find_email():
    email = request.json['user_email']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT user_id from user WHERE email = %s"
            cursor.execute(sql,(email))
            result = cursor.fetchone()
        if result == None:
            return 'pass'
        elif email == 'jlwinick@gmail.com':
            return 'pass'
        else:
            return 'fail'
    except:
        return 'fail'
        # if result == None:
        #     return 'None'
        # else:
        #     result = result['user_id']
        #     result = str(result)
        #     return result
    finally:
        connection.close()



@bp.route('/find_username',methods=['POST'])
def find_username():
    username = request.json['user_name']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT user_id from user WHERE username = %s"
            cursor.execute(sql,(username))
            result = cursor.fetchone()
            if result == None:
                return 'pass'
            else:
                return 'fail'
    except:
        return 'fail'
    finally:
        connection.close()

@bp.route('/post_login',methods=['POST'])
def post_login():
    username = request.json['user_name']
    psw = request.json['psw']

    connection = getConnection()

    #if user enters username only
    if len(username) > 0:
        try:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM user WHERE username = %s"
                cursor.execute(sql,(username))
                row = cursor.fetchone()

            if row == None:
                with connection.cursor() as cursor:
                    sql = "SELECT * FROM user WHERE email = %s"
                    cursor.execute(sql,(username))
                    row = cursor.fetchone()

            user = User(row['user_id'])
            pwhash = row['password_hash']
        except:
            return 'invalid'
        finally:
            connection.close()
        if user == None:
            return 'username invalid'
        # elif row['is_confirmed'] != 1:
        #     # send_confirm_register_email(row['user_id'])
        #     return 'unconfirmed'
        elif check_password_hash(pwhash=pwhash,password=psw) == True:
            login_user(user)
            return 'pass'
        else:
            return 'invalid password'
    else:
        return 'empty'


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'],defaults={'demo_code':None})
@bp.route('/register/demo_code', methods=['GET', 'POST'])
def register(demo_code):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('auth/register.html',demo_code=demo_code, title='Register')


@bp.route('/signup',methods=['POST'])
def signup():
    email = request.json['user_email']
    username = request.json['user_name']
    psw = request.json['psw']
    demo = request.json['demo']
    print(demo)
    print(email)
    print(username)
    print(psw)


    demo_code = demo['demo_code']


    password = generate_password_hash(psw)
    connection = getConnection()

    try:
        with connection.cursor() as cursor:
            sql = 'SELECT demo_code, email, demo_id FROM demo WHERE email = %s AND demo_code = %s'
            cursor.execute(sql,(email,demo_code))
            result = cursor.fetchone()
            print(result)

        if result == None:
            return 'demo_code'
        elif result['email'] != email:
            return 'demo_code'
        else:
            demo_id = result['demo_id']

            with connection.cursor() as cursor:
                sql = 'SELECT user_id FROM `user` WHERE email = %s'
                print(sql)
                cursor.execute(sql,(email))
                row = cursor.fetchone()

            print(row)

            if row is not None and row['user_id'] != 3:
                return 'duplicate email'

            with connection.cursor() as cursor:
                sql = 'SELECT user_id FROM `user` WHERE username = %s'
                print(sql)
                cursor.execute(sql,(username))
                row = cursor.fetchone()

            print(row)

            if row is not None:
                return 'duplicate username'

            with connection.cursor() as cursor:
                sql = "INSERT INTO user (username, email, password_hash,is_confirmed,demo_id) VALUES (%s,%s,%s,%s,%s)"
                cursor.execute(sql,(username,email,password,0,demo_id))
                connection.commit()

            result = dict()

            result['email'] = email
            result['username'] = username

            return jsonify(result)
    except:
        return 'fail'
    finally:
        connection.close()

    return 'Great success'


@bp.route('/update_password', methods=['POST'])
def update_password():
    user_id = request.json['user_id']
    password = request.json['psw']

    password_hash = generate_password_hash(password)
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = 'UPDATE user SET password_hash = %s WHERE user_id = %s'
            cursor.execute(sql,(password_hash,user_id))
            connection.commit()
    finally:
        connection.close()

    return redirect(url_for('main.index'))

@bp.route('/reset_password_request',methods=['GET','POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('auth/reset_password_request.html',title='Reset Password')

@bp.route('/send_confirm_register_token', methods=['POST'])
def send_confirm_register_token():
    user_id = int(request.json['user_id'])

    token = jwt.encode({'confirm_register': user_id, 'exp': time() + 36000},current_app.config['SECRET_KEY'], algorithm='HS256')

    send_confirm_register_email(user_id,token)

    return str(user_id)



@bp.route('/send_reset_password_token',methods=['POST'])
def send_reset_password_token():
    user_id = int(request.json['user_id'])

    token = jwt.encode({'reset_password': user_id, 'exp': time() + 36000},current_app.config['SECRET_KEY'], algorithm='HS256')

    send_password_reset_email(user_id,token)

    return str(user_id)


@bp.route('/confirm_register/<token>/', methods=['GET', 'POST'])
def confirm_register(token):

    output = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    user_id = output['confirm_register']
    user = User(user_id)

    if user_id:
        connection = getConnection()
        try:
            with connection.cursor() as cursor:
                sql = "UPDATE user SET is_confirmed = 1 WHERE user_id = %s"
                cursor.execute(sql,(user_id))
                connection.commit()
                login_user(user)
        except:
            login_type = 'invalid'
        finally:
            connection.close()

    return redirect(url_for('main.index',view='dashboard',theme='welcome'))


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    output = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    user_id = output['reset_password']

    if user_id:
        return render_template('auth/reset_password.html',user_id=user_id)
    else:
        return render_template('auth/login.html',type='invalid')

@bp.route('/reset_get_id',methods=['POST'])
def reset_get_id():
    email = str(request.json['email'])
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """SELECT `user_id` FROM `user` WHERE `email` = %s AND `created` IS NOT NULL ORDER BY `created` ASC LIMIT 1"""
            cursor.execute(sql,(email))
            row = cursor.fetchone()
            user_id = str(row['user_id'])
    finally:
        connection.close()

    if user_id:
        return user_id
    else:
        return 'fail'


@bp.route('/register_get_id', methods=['POST'])
def register_get_id():
    email = str(request.json['email'])
    username = str(request.json['username'])

    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql="""SELECT `user_id` FROM `user` WHERE `email` = %s AND `username` = %s"""
            cursor.execute(sql,(email,username))
            row = cursor.fetchone()
            user_id = str(row['user_id'])
    finally:
        connection.close()

    if user_id:
        return user_id
    else:
        return 'fail'



    # if current_user.is_authenticated:
    #     return redirect(url_for('main.index'))
    # user = User.verify_confirm_register_token(token)
    # if not user:
    #     flash('Link not valid!')
    #     return redirect(url_for('auth.login'))
    # else:
    #     user_id = user.get_id()
    #     connection = getConnection()
    #     try:
    #         with connection.cursor() as cursor:
    #             sql = 'UPDATE user SET is_confirmed = 1 WHERE user_id = %s'
    #             cursor.execute(sql,(user_id))
    #         connection.commit()
    #     finally:
    #         connection.close()
    #     flash('Registeration confirmed!')
    #     return redirect(url_for('auth.login'))

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    return render_template('auth/change_password.html')

@bp.route('/verify_password',methods=['POST'])
def verify_password():
    password = request.json['psw']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """SELECT user_id, password_hash FROM user WHERE user_id = %s
            """
            cursor.execute(sql,(current_user.id))
            row = cursor.fetchone()
            pwhash = row['password_hash']
    except:
        return 'fail'
    finally:
        connection.close()
    if row == None:
        return 'fail'
    elif check_password_hash(pwhash=pwhash,password=password) == True:
        return 'pass'
    else:
        return 'fail'


@bp.route('/post_change_password',methods=['POST'])
def post_change_password():
    old_psw = request.json['old_psw']
    new_psw = request.json['new_psw']
    psw_2 = request.json['psw_2']

    connection = getConnection()
    print(old_psw)
    print(new_psw)
    print(psw_2)
    try:
        with connection.cursor() as cursor:
            sql = """SELECT user_id, password_hash FROM user WHERE user_id = %s
            """
            cursor.execute(sql,(current_user.id))
            row = cursor.fetchone()
            print(row)
    except:
        return 'fail'

    finally:
        connection.close()

    if row == None:
        return 'incorrect'
    elif check_password_hash(pwhash=row['password_hash'],password=old_psw) == False:
        print('incorrect')
        return 'incorrect'
    elif len(new_psw) < 4:
        print('invalid')
        return 'invalid'
    elif new_psw != psw_2:
        print('no match')
        return 'no match'
    else:
        connection = getConnection()
        try:
            with connection.cursor() as cursor:
                sql = 'UPDATE user SET password_hash = %s WHERE user_id = %s'
                cursor.execute(sql,(generate_password_hash(new_psw),current_user.id))
                connection.commit()
        except:
            return 'fail'
        finally:
            return 'pass'
            connection.close()




# @bp.route('/reset_password/<token>',methods=['GET', 'POST'])
# def reset_password(token):
#     return render_template('auth/reset_password.html',title='Reset Password')

@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(basedir, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
