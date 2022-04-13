import json
from datetime import datetime, timedelta, date
from flask import render_template, flash, redirect, url_for, request, current_app, g, \
    jsonify, current_app, send_from_directory, jsonify
from flask_login import current_user, login_required
from app.models import User, load_user
from app.main import bp
from app import login
import urllib, hashlib
#import libgravatar
from app.splitter import poker_split
from app.myconnutils import getConnection
import pymysql.cursors
from flask_mail import Message
from app import mail, basedir
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from os import listdir
from os.path import isfile, join
import random
import string
import pdfkit
import numpy as np
from twilio.rest import Client
from app.email import send_email
import glob
import base64
import requests
import pandas as pd


account_sid = '*****'
auth_token = '*****'
client = Client(account_sid, auth_token)

def text(body):
    message = client.messages.create(
      messaging_service_sid='****',
      body=body,
      to='****'
    )
    return message.sid


#general functions
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



shopifyauth = '*******'
shopifyheaders = {'Authorization': 'Basic {token}'.format(token=base64.b64encode(shopifyauth.encode()).decode('ascii')), 'Content-Type': 'application/json'}

def get_all_products():
    url = "https://sipsend.myshopify.com/admin/api/2020-07/products.json?limit=250"
    r = requests.get(url, headers=shopifyheaders)
    obj = r.json()['products']
    return obj

def get_all_orders():
    url = "https://sipsend.myshopify.com/admin/api/2020-07/orders.json?status=any&limit=250"
    r = requests.get(url, headers=shopifyheaders)
    obj = r.json()['orders']
    return obj


def format_thousand(x):
        return "${:.1f}K".format(x/1000)


def monthly_revenue():
    orders = get_all_orders()
    orders = pd.json_normalize(orders)
    orders['created'] = pd.to_datetime(orders['created_at'],utc=True)
    orders['Month'] = orders['created'].dt.strftime('%b-%y')
    orders['total_price'] = pd.to_numeric(orders['total_price'])
    grouped_orders = orders.groupby(['Month'])['total_price'].sum().reset_index(name='Price').sort_values(by=['Price'],ascending=False)
    grouped_orders['Revenue'] = grouped_orders['Price'].apply(format_thousand)

    json = pd.DataFrame.to_json(grouped_orders,orient='split')
    return json

@bp.route('/pull_recap',methods=['POST'])
def pull_recap():
    monthly_rev = monthly_revenue()
    return {'monthly_rev':monthly_rev}

@bp.route('/recap',methods=['GET','POST'])
def recap():
    return render_template('recap.html')


@bp.route('/<demo_code>', methods=['GET', 'POST'])
@bp.route('/', methods=['GET', 'POST'], defaults={'demo_code':'None'})
def index(demo_code):

    print('Demo code: '+demo_code)
    try:
        user = get_user(current_user.id)
    except:
        user = None

    print('User id: '+str(user))

    connection = getConnection()

    try:
        if user is None and demo_code is not None:
            try:
                with connection.cursor() as cursor:
                    sql = 'SELECT demo_id, demo_code, email, company_name FROM `demo` WHERE `demo_code` = %s'
                    cursor.execute(sql,(demo_code))
                    demo = cursor.fetchone()
                    print(demo)
                if demo is not None:
                    demo = json.dumps(demo)
                    print(demo)
            except:
                demo = None
        else:
            demo = None




        with connection.cursor() as cursor:
            sql = """
                SELECT o.order_id
                FROM `order` o
                LEFT JOIN `company` c ON o.company_id = c.company_id
                LEFT JOIN `image` i ON c.image_id = i.image_id
                WHERE o.example = 1 AND i.user_id = 3
                """
            cursor.execute(sql)
            rows = cursor.fetchall()

        example_ids = []

        for x in range(len(rows)):
            row = rows[x]
            order_id = row['order_id']
            example_ids.append(order_id)

        example_ids = json.dumps({'example_ids':example_ids})

    except:
        example_ids = None

    finally:
        connection.close()

    basedir = os.path.abspath(os.path.dirname(__file__))
    l = basedir.split('/')[:-1]
    l.append('templates')
    x = '/'.join(l)
    mylist = glob.glob(x + '/index_*.html')
    mylist.sort(key=os.path.getmtime)
    name = mylist[len(mylist)-1]
    template_name = os.path.basename(name)
    return render_template(template_name, title='Dashboard',user=user,example_ids=example_ids,demo=demo)


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


@bp.route('/new-po', methods=['GET', 'POST'],defaults={"js": "plain"})
@bp.route("/<any(plain, jquery, fetch):js>")
@login_required
def new_po(js):
    return render_template('new-po.html',js=js,user_id=current_user.id)


@bp.route('/membership',methods=['GET','POST'])
def membership():
    return render_template('membership.html')


@bp.route('/confirm_existing_company',methods=['POST'])
def confirm_existing_company():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT image_id FROM image WHERE user_id = %s'
            cursor.execute(sql,(current_user.id))
            row = cursor.fetchone()
    finally:
        connection.close()

    if row == None:
        return 'pass'
    else:
        return 'fail'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['pdf', 'png', 'jpg', 'jpeg']






@bp.route('/upload_logo', methods=['POST'],defaults={"company_id":"None"})
@bp.route('/upload_logo/<company_id>', methods=['POST'])
def upload_logo(company_id):
    if request.method == 'POST':
        connection = getConnection()
        image_id = None

        try:
            #if user includes new image
            if 'file' in request.files:
                file = request.files['file']
                filename = file.filename

                #if file is ok, save image and add entry to image table
                if filename != '' and allowed_file(file.filename) == True:
                    extension = os.path.splitext(filename)[1]

                    #get next available filename
                    with connection.cursor() as cursor:
                        sql = """
                        SELECT max(`image_name`) AS `image_name` FROM `image`
                        """
                        cursor.execute(sql)
                        row = cursor.fetchone()

                    image_name = int(row['image_name'])+1

                    with connection.cursor() as cursor:
                        sql = """
                        INSERT INTO `image` (`extension`,`user_id`,`image_name`) VALUES (%s,%s,%s)
                        """
                        cursor.execute(sql,(extension,current_user.id,image_name))
                        connection.commit()

                    with connection.cursor() as cursor:
                        sql = """
                        SELECT `user_id` AS `user_id`,max(`image_id`) AS `image_id` FROM `image` WHERE `user_id` = %s GROUP BY `user_id`
                        """
                        cursor.execute(sql,(current_user.id))
                        row = cursor.fetchone()

                    image_id = row['image_id']

                    x = os.path.join(basedir,'static','uploads',str(image_name)+extension)
                    file.save(x)

            elif company_id != 'None':
                #if we are editing, use previous image by default
                with connection.cursor() as cursor:
                    sql = """
                    SELECT i.image_name AS `image_name`, i.image_id AS `image_id`, i.extension AS `extension` FROM `company` c LEFT JOIN `image` i ON c.image_id = i.image_id WHERE c.company_id = %s
                    """
                    cursor.execute(sql,(company_id))
                    row = cursor.fetchone()
                    image_name = row['image_name']

                with connection.cursor() as cursor:
                    sql = """
                    INSERT INTO `image` (`extension`,`user_id`,`image_name`) VALUES (%s,%s,%s)
                    """
                    cursor.execute(sql,(row['extension'],current_user.id,row['image_name']))
                    connection.commit()

                with connection.cursor() as cursor:
                    sql = """
                    SELECT `user_id` AS `user_id`, max(`image_id`) AS `image_id` FROM `image` WHERE `user_id` = %s GROUP BY `user_id`
                    """
                    cursor.execute(sql,(current_user.id))
                    row = cursor.fetchone()

                image_id = row['image_id']

            elif company_id == 'None':
                #first check if empty image exists
                with connection.cursor() as cursor:
                    sql = """
                    SELECT i.image_id AS `image_id` FROM `image` i WHERE i.extension IS NULL AND i.user_id = %s LIMIT 1
                    """
                    cursor.execute(sql,(current_user.id))
                    row = cursor.fetchone()
                    try:
                        image_id = row['image_id']
                    except:
                        with connection.cursor() as cursor:
                            sql = """
                            INSERT INTO `image` (`user_id`) VALUES (%s)
                            """
                            cursor.execute(sql,(current_user.id))
                            connection.commit()

                        with connection.cursor() as cursor:
                            sql = """
                            SELECT i.user_id AS `user_id`, MAX(i.image_id) AS `image_id` FROM `image` i WHERE i.user_id = %s GROUP BY i.user_id
                            """
                            cursor.execute(sql,(current_user.id))
                            row = cursor.fetchone()
                            image_id = row['image_id']

        finally:
            connection.close()

        return str(image_id)
    else:
        return 'post only'


@bp.route('/get_access',methods=['POST'])
def get_access():
    order_id = request.json['order_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """SELECT `access_code` FROM `order` WHERE order_id = %s"""
            cursor.execute(sql,(order_id))
            row = cursor.fetchone()
            access_code = row['access_code']
    finally:
        connection.close()

    order_info = dict()

    order_info['order_id'] = order_id
    order_info['access_code'] = access_code

    return jsonify(order_info)




@bp.route('/update_po',methods=['POST'])
def update_po():

    order_id = request.json['order_id']
    access_code = request.json['access_code']
    inputs = request.json['inputs']
    items = request.json['items']


    connection = getConnection()
    try:
        #check if this is an example order
        with connection.cursor() as cursor:
            sql = "SELECT `order_id` FROM `order` WHERE `example` = %s"
            cursor.execute(sql,(1))
            example_rows = cursor.fetchall()
    finally:
        connection.close()

    example_ids = []

    for x in range(len(example_rows)):
        row = example_rows[x]
        example_order_id = str(row['order_id'])
        example_ids.append(example_order_id)

    if str(order_id) in example_ids:
        return post_po_function(inputs=inputs,items=items)
    else:
        return update_po_function(order_id=order_id,access_code=access_code,inputs=inputs,items=items)

def build_po(inputs=None,items=None):
        #unpack items
    dicts = dict()

    clean_item_array = []
    if items is not None:
        for x in range(len(items)):
            item = items[x]
            clean_dict = dict()
            for (key,value) in item.items():
                try:
                    float(value)
                    clean_dict[key] = value
                except ValueError:
                    if value != '':
                        clean_dict[key] = str(value)
            clean_item_array.append(clean_dict)

        dicts['clean_item_array'] = clean_item_array


    if inputs is not None:
        input_dict = {}
        for x in range(len(inputs)):
            y = inputs[x]
            input_dict[y['id']] = y['value']

        columns = list(input_dict.keys())
        values = list(input_dict.values())

        clean_input_dict = {}

        for(key,value) in input_dict.items():
            if value != '':
                clean_input_dict[key] = value

        company_dict = dict()
        supplier_dict = dict()
        recipient_dict = dict()
        order_dict = dict()
        sku_dict = dict()

        for (key, value) in clean_input_dict.items():
           # Check if key is even then add pair to new dictionary

            if key.startswith('company_setup_') == True:
                key = key.split('_',2)[2]
                company_dict[key] = value
            elif key.startswith('company_') == True:
                key = key.split('_',1)[1]
                company_dict[key] = value
            elif key == 'image_id':
                company_dict[key] = value
            elif key.startswith('supplier_') == True:
                key = key.split('_',1)[1]
                supplier_dict[key] = value
            elif key.startswith('recipient_') == True:
                key = key.split('_',1)[1]
                recipient_dict[key] = value
            elif key.startswith('sku_') == True:
                key = key.split('_',1)[1]
                sku_dict[key] = value
            else:
                order_dict[key] = value


        dicts['company_dict'] = company_dict
        dicts['supplier_dict'] = supplier_dict
        dicts['recipient_dict'] = recipient_dict
        dicts['order_dict'] = order_dict
        dicts['sku_dict'] = sku_dict

    return dicts



def update_po_function(order_id,access_code,inputs,items):
    #unpack items
    dicts = build_po(inputs=inputs,items=items)
    # order_columns = ', '.join(['`{}`'.format(w) for w in list(order_dict.keys())])
    # order_values = ', '.join(["'{}'".format(w) for w in list(order_dict.values())])
    company_dict = dicts['company_dict']
    supplier_dict = dicts['supplier_dict']
    recipient_dict = dicts['recipient_dict']
    order_dict = dicts['order_dict']
    status_dict = dicts['status_dict']
    clean_item_array = dicts['clean_item_array']

    #add user_id to dicts
    company_dict['user_id'] = str(current_user.id)
    supplier_dict['user_id'] = str(current_user.id)
    recipient_dict['user_id'] = str(current_user.id)

    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT l.supplier_id AS `supplier_id`
            ,c.company_id AS `company_id`
            ,r.recipient_id AS `recipient_id`
            FROM `order` o
            INNER JOIN company c ON o.company_id = c.company_id AND (c.user_id = 3 OR o.example = 1)
            LEFT JOIN `recipient` r ON o.recipient_id = r.recipient_id AND r.active = 1
            LEFT JOIN (SELECT t.order_id AS `order_id`, MAX(t.supplier_id) AS `supplier_id`, MAX(t.supplier_name) AS `supplier_name`, MAX(t.line_item) AS `line_item`, COUNT(*) AS `sku_count` FROM (SELECT o.order_id AS `order_id` ,sk.sku_id AS `sku_id`, MAX(sp.supplier_id) AS `supplier_id`, MAX(sp.name) AS `supplier_name`, MAX(sk.cost) AS `cost`, MAX(sk.quantity) AS `quantity`, MAX(sk.cost)*MAX(sk.quantity) AS `line_item` FROM supplier sp LEFT JOIN `sku` sk ON sp.supplier_id = sk.supplier_id LEFT JOIN `cart` ct ON sk.sku_id = ct.sku_id LEFT JOIN `order` o ON ct.order_id = o.order_id WHERE sp.user_id = %s AND sp.active = 1 AND sk.active = 1 AND ct.active = 1 AND o.active = 1 GROUP BY o.order_id, sk.sku_id) `t` GROUP BY t.order_id) `l` ON o.order_id = l.order_id WHERE o.order_id = %s
            """
            cursor.execute(sql,(current_user.id,order_id))
            idxs = cursor.fetchone()


        with connection.cursor() as cursor:
            sql = 'UPDATE `order` SET {} WHERE `order_id`=%s;'.format(', '.join('`{}`=%s'.format(k) for k in order_dict))
            #print('update order sql: '+str(sql))

            #print(order_dict)
            #print(order_id)
            order_values = list(order_dict.values())
            order_values.append(order_id)
            cursor.execute(sql,(order_values))
            connection.commit()
            #print('order values: '+str(values))

        #add order_id into other dicts
        # company_dict['order_id'] = order_id
        # supplier_dict['order_id'] = order_id
        # recipient_dict['order_id'] = order_id

        status_dict['order_id'] = order_id

        # print(item_columns_array)
        #print(item_columns_array)

        #sql for inserting skus
        # print('test')
        # print(len(item_columns_array))

        #print('item count: '+str(len(clean_item_array)))
        #query what items are currently associated with this order_id
        with connection.cursor() as cursor:
            sql = """
            SELECT sk.sku_id AS `sku_id`
            ,sk.foreign_id AS `foreign_id`
            ,ct.cart_id AS `cart_id`
            FROM cart ct
            LEFT JOIN sku sk ON ct.sku_id = sk.sku_id
            WHERE ct.order_id = %s
            AND ct.active = 1
            AND sk.active = 1
            """
            cursor.execute(sql,(order_id))
            sku_rows = cursor.fetchall()
        #print('existing skus: '+str(sku_rows))
        # print('current sku rows: '+str(sku_rows))
        # print('new sku rows: '+str(clean_item_array))

        #build list of new foreign ids
        new_sku_ids = []

        for x in range(len(clean_item_array)):
            sku = clean_item_array[x]
            foreign_id = sku['foreign_id']
            new_sku_ids.append(foreign_id)

        #print('new ids: '+str(new_sku_ids))


        #bulid list of existing foreign ids
        existing_sku_ids = []
        index_list = []

        for x in range(len(sku_rows)):
            sku = sku_rows[x]
            foreign_id = sku['foreign_id']
            existing_sku_ids.append(foreign_id)
            try:
                index = new_sku_ids.index(foreign_id)
            except ValueError:
                index = None
            index_list.append(index)


        #index of existing id in new ids


        #print('existing ids: '+str(existing_sku_ids))

        #print('sku count: '+str(len(sku_rows)))

        #loop through existing skus and update or delete rows
        #print('existing sku length: '+str(len(existing_sku_ids)))
        for x in range(len(sku_rows)):
            index = index_list[x]
            #print('Index: '+str(index))
            row = sku_rows[x]
            #print('Row: '+str(row))
            foreign_id = row['foreign_id']
            sku_id = row['sku_id']
            cart_id = row['cart_id']
            #handle existing skus
            #print('Index: '+str(index))
            if index != None:
                #print('update')

                new_sku = clean_item_array[index]

                #print('new sku: '+str(new_sku))

                #remove foreign id from new sku dictionary
                new_sku.pop('foreign_id', None)
                #print('new sku: '+str(new_sku))
                with connection.cursor() as cursor:
                    sql = 'UPDATE `sku` SET {} WHERE `sku_id` = %s'.format(', '.join('`{}`=%s'.format(k) for k in new_sku))
                    #print('update existing sku sql: '+str(sql))
                    values = list(new_sku.values())
                    values.append(sku_id)
                    cursor.execute(sql,(values))
                    connection.commit()
            else:
               # print('delete')
                with connection.cursor() as cursor:
                    sql = "UPDATE `cart` SET `active` = 0 WHERE order_id = %s AND sku_id = %s"
                    #print('delete sku sql: '+str(sql))
                    cursor.execute(sql,(order_id,sku_id))
                    connection.commit()
        #print('test 4')
        #handle new skus
        for x in range(len(clean_item_array)):
            new_sku = clean_item_array[x]
            #print('add')
            sku_columns = ', '.join(['`{}`'.format(w) for w in list(new_sku.keys())])
            sku_values = ', '.join(['%s']*len(list(new_sku.values())))
            #print('sku columns: '+str(sku_columns))
            #print('sku values: '+str(sku_values))
            with connection.cursor() as cursor:
                sql = "INSERT INTO `sku` ("+sku_columns+")"+" VALUES ("+sku_values+")"
                #print('add new sku sql: '+str(sql))
                cursor.execute(sql,(list(new_sku.values())))
                connection.commit()

        #sql for updating company
        company_columns = ', '.join(['`{}`'.format(w) for w in list(company_dict.keys())])
        length = len(list(company_dict.values()))
        value_input = ', '.join(['%s']*length)

        with connection.cursor() as cursor:
            sql = 'UPDATE `company` SET {} WHERE `company_id` = %s'.format(', '.join('{}=%s'.format(k) for k in company_dict))
            #print(sql)
            values = list(company_dict.values())
            values.append(idxs['company_id'])
            cursor.execute(sql,(list(values)))
            connection.commit()

        #sql for updating supplier
        with connection.cursor() as cursor:
            sql = 'UPDATE `supplier` SET {} WHERE `supplier_id` = %s'.format(', '.join('{}=%s'.format(k) for k in supplier_dict))
            values = list(supplier_dict.values())
            values.append(idxs['supplier_id'])
            #print(sql)
            cursor.execute(sql,(list(values)))
            connection.commit()


        # sql for updating recipient
        with connection.cursor() as cursor:
            sql = 'UPDATE `recipient` SET {} WHERE `recipient_id` = %s'.format(', '.join('`{}`=%s'.format(k) for k in recipient_dict))
            #print(sql)
            values = list(recipient_dict.values())
            values.append(str(idxs['recipient_id']))
            #print(values)
            cursor.execute(sql,(values))
            connection.commit()

        #sql for updating

        status_columns = ', '.join(['`{}`'.format(w) for w in list(status_dict.keys())])

        status_values = ', '.join(['%s']*len(list(status_dict.values())))


        with connection.cursor() as cursor:
            sql = "INSERT INTO `status` ("+status_columns+") VALUES ("+status_values+")"
            #print(sql)
            cursor.execute(sql,list(status_dict.values()))
            connection.commit()


    finally:
        connection.close()
        output = {
            'order_id':str(order_id),
            'access_code':access_code
        }
        return jsonify(output)
    return 'fail'



@bp.route('/post_recipient',methods=['post'])
def post_recipient():
    inputs = request.json['inputs']

    input_dict = {}
    for x in range(len(inputs)):
        y = inputs[x]
        input_dict[y['id']] = y['value']

    recipient_id = input_dict.pop('recipient_id')

    input_dict['modified'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    connection = getConnection()
    if recipient_id != '':
        try:
            recipient_values = list(input_dict.values())
            recipient_values.append(recipient_id)
            with connection.cursor() as cursor:
                sql = 'UPDATE `recipient` SET {} WHERE `recipient_id`=%s;'.format(', '.join('`{}`=%s'.format(k) for k in input_dict))
                print(sql)
                print(supplier_values)
                cursor.execute(sql,(recipient_values))
                connection.commit()

        finally:
            connection.close()
    else:
        input_dict['user_id'] = current_user.id
        columns = ', '.join(['`{}`'.format(w) for w in list(input_dict.keys())])
        values = ', '.join(['%s']*len(list(input_dict.values())))
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO `recipient` ("+columns+")"+" VALUES ("+values+")"
                cursor.execute(sql,(list(input_dict.values())))
                connection.commit()
        finally:
            connection.close()
    return str(recipient_id)



@bp.route('/post_supplier',methods=['POST'])
def post_supplier():
    inputs = request.json['inputs']

    input_dict = {}
    for x in range(len(inputs)):
        y = inputs[x]
        input_dict[y['id']] = y['value']

    supplier_id = input_dict.pop('supplier_id')

    input_dict['modified'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    connection = getConnection()
    if supplier_id != '':
        try:
            supplier_values = list(input_dict.values())
            supplier_values.append(supplier_id)
            with connection.cursor() as cursor:
                sql = 'UPDATE `supplier` SET {} WHERE `supplier_id`=%s;'.format(', '.join('`{}`=%s'.format(k) for k in input_dict))
                print(sql)
                print(supplier_values)
                cursor.execute(sql,(supplier_values))
                connection.commit()

        finally:
            connection.close()
    else:
        input_dict['user_id'] = current_user.id
        columns = ', '.join(['`{}`'.format(w) for w in list(input_dict.keys())])
        values = ', '.join(['%s']*len(list(input_dict.values())))
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO `supplier` ("+columns+")"+" VALUES ("+values+")"
                cursor.execute(sql,(list(input_dict.values())))
                connection.commit()
        finally:
            connection.close()
    return str(supplier_id)


@bp.route('/load_recurring',methods=['POST'])
def load_recurring():
    connection = getConnection()

    try:
        with connection.cursor() as cursor:
            sql =  """
            SELECT
            r.recurring_id AS `recurring_id`
            ,o.order_id AS `order_id`
            ,o.foreign_id AS `foreign_id`
            ,sp.supplier_id AS `supplier_id`
            ,sp.name AS `supplier_name`
            ,r.frequency AS `frequency`
            FROM `recurring` r
            LEFT JOIN `order` o ON r.order_id = o.order_id
            LEFT JOIN (SELECT ct.order_id, MAX(ct.sku_id) AS `sku_id` FROM cart ct GROUP BY ct.order_id) ct ON o.order_id = ct.order_id
            LEFT JOIN `sku` sk ON ct.sku_id = sk.sku_id
            LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            WHERE sp.user_id = %s
            AND r.active = %s
            ORDER BY r.created DESC
            """
            cursor.execute(sql,(current_user.id,1))
            result = cursor.fetchall()

        clean_result = []

        for x in range(len(result)):
            dirty = result[x]
            clean = {key: str(value) for key, value in dirty.items()}
            clean_result.append(clean)

    finally:
        connection.close()
    return {'recurring':clean_result}

@bp.route('/post_recurring',methods=['POST'])
def post_recurring():
    order_id = request.json['order_id']
    frequency = request.json['frequency']

    connection = getConnection()

    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO `recurring` (`order_id`,`frequency`) VALUES (%s,%s)"
            cursor.execute(sql,(int(order_id),int(frequency)))
            connection.commit()
    finally:
        connection.close()
    return 'Great success'

@bp.route('/remove_recurring',methods=['POST'])
def remove_recurring():
    recurring_id = request.json['recurring_id']

    connection = getConnection()

    try:
        with connection.cursor() as cursor:
            sql = "UPDATE `recurring` SET `active`=0 WHERE `recurring_id` = %s "
            cursor.execute(sql,(recurring_id))
            connection.commit()

    finally:
        connection.close()
    return recurring_id

@bp.route('/edit_recurring',methods=['POST'])
def edit_recurring():
    recurring_id = request.json['recurring_id']
    order_id = request.json['order_id']
    frequency = request.json['frequency']

    connection = getConnection()

    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM `recurring` WHERE `recurring_id` = %s"
            cursor.excute(sql,recurring_id)
            row = cursor.fetchone()

        with connection.cursor() as cursor:
            sql = "INSERT INTO `recurring` (`created`,`order_id`,`active`,`frequency`) VALUES (%s,%s,%s,%s)"
            cursor.execute(sql,(row['created'],order_id,1,frequency))
            connection.commit()

        with connection.cursor() as cursor:
            sql = "UPDATE `recurring` SET `active`=0 WHERE `recurring_id` = %s "
            cursor.execute(sql,(recurring_id))
            connection.commit()


    finally:
        connection.close()
    return recurring_id


@bp.route('/post_company',methods=['POST'])
def post_company():
    inputs = request.json['inputs']
    print(inputs)


    input_dict = {}
    for x in range(len(inputs)):
        y = inputs[x]
        print(y)
        input_dict[y['id']] = str(y['value'])

    company_id = input_dict.pop('company_id')

    connection = getConnection()
    if company_id != '':
        try:
            company_values = list(input_dict.values())
            company_values.append(company_id)
            with connection.cursor() as cursor:
                sql = 'UPDATE `company` SET {} WHERE `company_id`=%s;'.format(', '.join('`{}`=%s'.format(k) for k in input_dict))
                print(sql)
                print(company_values)
                cursor.execute(sql,(company_values))
                connection.commit()
        finally:
            connection.close()
    else:
        try:
            columns = ', '.join(['`{}`'.format(w) for w in list(input_dict.keys())])
            values = ', '.join(['%s']*len(list(input_dict.values())))
            with connection.cursor() as cursor:
                sql = "INSERT INTO `company` ("+columns+")"+" VALUES ("+values+")"
                cursor.execute(sql,(list(input_dict.values())))
                connection.commit()

            with connection.cursor() as cursor:
                sql = "SELECT c.company_id AS `company_id` FROM `company` c LEFT JOIN `image`i ON c.image_id=i.image_id WHERE i.user_id = %s ORDER BY c.created DESC LIMIT 1"
                cursor.execute(sql,(current_user.id))
                row = cursor.fetchone()
            company_id = row['company_id']
        finally:
            connection.close()

    return str(company_id)





@bp.route('/post_sku',methods=['POST'])
def post_sku():
    inputs = request.json['inputs']

    input_dict = {}
    for x in range(len(inputs)):
        y = inputs[x]
        input_dict[y['id']] = y['value']

    sku_id = input_dict.pop('sku_id')

    input_dict['modified'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    connection = getConnection()
    if sku_id != '':
        try:
            sku_values = list(input_dict.values())
            sku_values.append(sku_id)
            with connection.cursor() as cursor:
                sql = 'UPDATE `sku` SET {} WHERE `sku_id`=%s;'.format(', '.join('`{}`=%s'.format(k) for k in input_dict))
                cursor.execute(sql,(sku_values))
                connection.commit()

        finally:
            connection.close()
    else:
        try:
            sku_columns = ', '.join(['`{}`'.format(w) for w in list(input_dict.keys())])

            sku_values = ', '.join(['%s']*len(list(input_dict.values())))

            with connection.cursor() as cursor:
                sql = "INSERT INTO `sku` ("+sku_columns+")"+" VALUES ("+sku_values+")"
                cursor.execute(sql,(list(input_dict.values())))
                connection.commit()
        finally:
            connection.close()
    return str(sku_id)

@bp.route('/post_group',methods=['POST'])
def post_group():
    skus = request.json['skus']
    name = request.json['name']


    ##validate skus
    #confirm sku_ids are ints
    clean_skus = [];
    for x in range(len(skus)):
        sku_id = skus[x]
        if sku_id.isnumeric():
            clean_skus.append(sku_id)

    if len(clean_skus) == 0:
        return 'no_skus'

    sku_id_placeholders = ', '.join(['%s']*len(clean_skus))

    #confirm sku_ids are owned by user
    connection = getConnection()
    try:

        try:
            with connection.cursor() as cursor:
                sql = 'SELECT sk.sku_id AS `sku_id` FROM `sku` sk LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id WHERE sk.active=1 AND sp.user_id = %s AND sk.sku_id IN ('+sku_id_placeholders+')'
                values = clean_skus
                values.insert(0,current_user.id)
                print(values)
                cursor.execute(sql,(values))
                rows = cursor.fetchall()
        except:
            return 'sku_fail'
        try:
            name = str(name)
            if len(name) == 0:
                return 'no_name'

            with connection.cursor() as cursor:
                sql = "INSERT INTO `sku_group` (`name`,`user_id`) VALUES (%s,%s)"
                cursor.execute(sql,(name,current_user.id))
                connection.commit()

            with connection.cursor() as cursor:
                sql = 'SELECT `sku_group_id` FROM `sku_group` WHERE `user_id` = %s ORDER BY created DESC LIMIT 1;'
                cursor.execute(sql,(current_user.id))
                sku_group_id = cursor.fetchone()['sku_group_id']
        except:
            return 'name_fail'
        try:
            for x in range(len(rows)):
                row = rows[x]
                sku_id = row['sku_id']
                with connection.cursor() as cursor:
                    sql = 'INSERT INTO `grouping` (`sku_id`,`sku_group_id`,`user_id`) VALUES (%s,%s,%s)'
                    cursor.execute(sql,(sku_id,sku_group_id,current_user.id))
                    connection.commit()

            return {'sku_group_id':sku_group_id,'skus':rows}
        except:
            return 'skus_fail'

    finally:
        connection.close()








    # connection = getConnection()
    # try:
    #     with connection.cursor() as cursor:
    #         sql = ''
    # finally:
    #     connection.close()
    return {'skus':skus}



@bp.route('/post_po',methods=['POST'])
def post_po():
    inputs = request.json['inputs']
    items = request.json['items']
    order_id = request.json['order_id']

    # print(inputs)
    # print(items)
    # print(po_type)

    connection = getConnection()

    input_dict = dict()
    for x in range(len(inputs)):
        input_val = inputs[x]
        input_dict[input_val['id']] = str(input_val['value'])


    if input_dict['delivered_date'] == 'None':
        input_dict.pop('delivered_date',None)


    if order_id == '':
        access_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        input_dict['access_code'] = access_code

        try:
            with connection.cursor() as cursor:
                sql = 'SELECT c.company_id AS `company_id` FROM `company` c LEFT JOIN `image` i ON c.image_id = i.image_id WHERE c.active = 1 AND i.user_id = %s'
                cursor.execute(sql,(current_user.id))
                row = cursor.fetchone()

            company_id = str(row['company_id'])
            input_dict['company_id'] = company_id
            order_columns = ', '.join(['`{}`'.format(w) for w in list(input_dict.keys())])
            order_values = ', '.join(['%s']*len(list(input_dict.values())))

            with connection.cursor() as cursor:
                sql = "INSERT INTO `order` ("+order_columns+")"+" VALUES ("+order_values+")"
                cursor.execute(sql,(list(input_dict.values())))
                connection.commit()

            with connection.cursor() as cursor:
                sql = """
                    SELECT o.order_id AS `order_id`
                    ,o.access_code AS `access_code`
                    FROM `order` o
                    LEFT JOIN `company` c ON o.company_id = c.company_id
                    LEFT JOIN `image` i ON c.image_id = i.image_id
                    WHERE i.user_id = %s
                    ORDER BY o.created DESC
                    LIMIT 1
                """
                cursor.execute(sql,(current_user.id))
                row = cursor.fetchone()

            order_id = row['order_id']
            access_code = row['access_code']

            sku_ids = []
            for x in range(len(items)):
                sku_id = items[x]['sku_id']
                sku_ids.append(sku_id)

            sku_values = ', '.join(['%s']*len(sku_ids))

            with connection.cursor() as cursor:
                sql = "SELECT `cost` FROM `sku` WHERE `sku_id` IN ("+sku_values+")"
                cursor.execute(sql,(sku_ids))
                costs = cursor.fetchall()

            for x in range(len(items)):
                item = items[x]

                item['cost'] = str(costs[x]['cost'])

                with connection.cursor() as cursor:
                    sql = "INSERT INTO `cart` (`sku_id`,`quantity`,`order_id`,`cost`) VALUES (%s,%s,%s,%s)"
                    cursor.execute(sql,(item['sku_id'],item['quantity'],order_id,str(item['cost'])))
                    connection.commit()
        finally:
            connection.close()

    else:
        try:
            order_columns = ', '.join(['`{}`'.format(w) for w in list(input_dict.keys())])
            order_values = list(input_dict.values())
            order_values.append(order_id)

            with connection.cursor() as cursor:
                sql = 'UPDATE `order` SET {} WHERE `order_id`=%s;'.format(', '.join('`{}`=%s'.format(k) for k in input_dict))
                cursor.execute(sql,order_values)
                connection.commit()

            with connection.cursor() as cursor:
                sql = 'DELETE FROM cart WHERE order_id = %s'
                cursor.execute(sql,(order_id))
                connection.commit()


            sku_ids = []
            for x in range(len(items)):
                sku_id = items[x]['sku_id']
                sku_ids.append(sku_id)

            sku_values = ', '.join(['%s']*len(sku_ids))

            with connection.cursor() as cursor:
                sql = "SELECT `cost` FROM `sku` WHERE `sku_id` IN ("+sku_values+")"
                cursor.execute(sql,(sku_ids))
                costs = cursor.fetchall()

            for x in range(len(items)):
                item = items[x]

                item['cost'] = str(costs[x]['cost'])

                with connection.cursor() as cursor:
                    sql = "INSERT INTO `cart` (`sku_id`,`quantity`,`order_id`,`cost`) VALUES (%s,%s,%s,%s)"

                    cursor.execute(sql,(item['sku_id'],item['quantity'],order_id,str(item['cost'])))
                    connection.commit()

        finally:
            connection.close()

    return str(order_id)


def post_po_function(inputs,items):
    #unpack items
    dicts = build_po(inputs=inputs,items=items)

    #print('post_po_function test dicts: '+str(dicts))
    #print('Dicts: '+str(dicts))
    company_dict = dicts['company_dict']
    supplier_dict = dicts['supplier_dict']
    recipient_dict = dicts['recipient_dict']
    order_dict = dicts['order_dict']
    status_dict = dicts['status_dict']

    clean_item_array = dicts['clean_item_array']

    #add user_id to dicts
    company_dict['user_id'] = str(current_user.id)
    supplier_dict['user_id'] = str(current_user.id)
    recipient_dict['user_id'] = str(current_user.id)

    #create a 10 character access code for each order
    access_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    order_dict['access_code'] = access_code

    #first insert data into company, supplier, and recipient tables. These primary ids are needed for inserting data into order and sku tables.

    company_columns = ', '.join(['`{}`'.format(w) for w in list(company_dict.keys())])
    company_values = ', '.join(['%s']*len(list(company_dict.values())))

    supplier_columns = ', '.join(['`{}`'.format(w) for w in list(supplier_dict.keys())])
    supplier_values = ', '.join(['%s']*len(list(supplier_dict.values())))

    recipient_columns = ', '.join(['`{}`'.format(w) for w in list(recipient_dict.keys())])
    recipient_values = ', '.join(['%s']*len(list(recipient_dict.values())))


    connection = getConnection()
    try:
        #sql for inserting company, supplier, recipient
        with connection.cursor() as cursor:
            sql = "INSERT INTO `company` ("+company_columns+")"+" VALUES ("+company_values+")"
            cursor.execute(sql,(list(company_dict.values())))
            connection.commit()

        with connection.cursor() as cursor:
            sql = "INSERT INTO `supplier` ("+supplier_columns+")"+" VALUES ("+supplier_values+")"
            cursor.execute(sql,(list(supplier_dict.values())))
            connection.commit()

        with connection.cursor() as cursor:
            sql = "INSERT INTO `recipient` ("+recipient_columns+")"+" VALUES ("+recipient_values+")"
            cursor.execute(sql,(list(recipient_dict.values())))
            connection.commit()

        #build dict of primary idexes to add to order table
        with connection.cursor() as cursor:
            sql = "SELECT max(c.company_id) AS `company_id`, max(sp.supplier_id) AS `supplier_id`, max(r.recipient_id) AS `recipient_id` FROM company c LEFT JOIN supplier sp ON c.user_id = sp.user_id LEFT JOIN recipient r ON c.user_id = r.user_id WHERE c.user_id = %s"
            cursor.execute(sql,(current_user.id))
            row = cursor.fetchone()

        #compile primary idxs of supplier, company, and recipient tables
        primary_idxs = {'company_id':row['company_id'],'recipient_id':row['recipient_id']}
        supplier_idx = {'supplier_id':row['supplier_id']}
        #add primary idexes to order table
        order_dict.update(primary_idxs)

        order_columns = ', '.join(['`{}`'.format(w) for w in list(order_dict.keys())])

        order_values = ', '.join(['%s']*len(list(order_dict.values())))

        #insert into orders
        with connection.cursor() as cursor:
            sql = "INSERT INTO `order` ("+order_columns+")"+" VALUES ("+order_values+")"
            cursor.execute(sql,(list(order_dict.values())))
            connection.commit()

        #get this order id by most recent with user_id
        with connection.cursor() as cursor:
            sql = "SELECT MAX(o.order_id) AS `order_id` FROM `order` o LEFT JOIN `company` c ON o.company_id = c.company_id LEFT JOIN `user` u ON c.user_id = u.user_id WHERE u.user_id = %s"
            cursor.execute(sql,(current_user.id))
            row = cursor.fetchone()

        order_id = row['order_id']

        for x in range(len(clean_item_array)):
            clean_item = clean_item_array[x]
            clean_item.update(supplier_idx)

            sku_columns = ', '.join(['`{}`'.format(w) for w in list(clean_item.keys())])

            sku_values = ', '.join(['%s']*len(list(clean_item.values())))

            with connection.cursor() as cursor:
                sql = "INSERT INTO `sku` ("+sku_columns+")"+" VALUES ("+sku_values+")"
                cursor.execute(sql,(list(clean_item.values())))
                connection.commit()

        #print('test 1')
        #get array of sku_ids so we can add to cart
        with connection.cursor() as cursor:
            #print('test 2')
            sql = "SELECT sk.sku_id AS `sku_id` FROM sku sk LEFT JOIN supplier sp ON sk.supplier_id = sp.supplier_id WHERE sp.user_id = %s ORDER BY sku_id DESC LIMIT %s;"
            cursor.execute(sql,(current_user.id,len(clean_item_array)))

            rows = cursor.fetchall()



        for x in range(len(rows)):
            row = rows[x]
            cart_dict = {'sku_id':str(row['sku_id']),'order_id':str(order_id)}


            cart_columns = ', '.join(['`{}`'.format(w) for w in list(cart_dict.keys())])

            cart_values = ', '.join(['%s']*len(list(cart_dict.values())))

            with connection.cursor() as cursor:
                sql = "INSERT INTO `cart` ("+cart_columns+")"+" VALUES ("+cart_values+")"
                cursor.execute(sql,(list(cart_dict.values())))
                connection.commit()


        status_dict['order_id'] = order_id

        status_columns = ', '.join(['`{}`'.format(w) for w in list(status_dict.keys())])

        status_values = ', '.join(['%s']*len(list(status_dict.values())))

        with connection.cursor() as cursor:
            sql = "INSERT INTO `status` ("+status_columns+") VALUES ("+status_values+")"
            cursor.execute(sql,list(status_dict.values()))
            connection.commit()


    finally:
        connection.close()
        output = {
            'order_id':str(order_id),
            'image_id':str(company_dict['image_id']),
            'access_code':access_code
        }
        return jsonify(output)
    return 'fail'


avoid_columns = ['supplier_id','user_id','created','modified','sku_id','company_id','active','order_date','mabd','image_id','recipient_id','ship_to_company','access_code','cart_id','order_id']

def unique(list1):

    # intilize a null list
    unique_list = []

    # traverse for all elements
    for x in list1:
        # check if exists in unique_list or not
        if x not in unique_list:
            unique_list.append(x)
    # print list
    return unique_list






@bp.route('/request_demo',methods=['POST'])
def request_demo():
    connection = getConnection()

    demo_input = request.json['input']

    demo_input = {key:value for (key,value) in demo_input.items() if value != ''}

    demo_input['demo_code'] = ''.join(random.choices(string.ascii_letters + string.digits, k=10))


    columns = ', '.join(['`{}`'.format(w) for w in list(demo_input.keys())])
    values = ', '.join(['%s']*len(list(demo_input.values())))



    text_body = ', '.join(['{}'.format(w) for w in [demo_input['first_name'],demo_input['last_name'],demo_input['email']]])
    'Demo request: '+text_body
    text_response = text(text_body)
    print(text_response)


    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO `demo` ("+columns+")"+" VALUES ("+values+")"
            print(sql)
            cursor.execute(sql,(list(demo_input.values())))
            connection.commit()
        return 'pass'
    except:
        return 'fail'
    finally:
        connection.close()



@bp.route('/post_examples',methods=['POST'])
def post_examples():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT c.* FROM `company` c LEFT JOIN `image` i ON c.image_id = i.image_id WHERE i.user_id = %s'
            cursor.execute(sql,(current_user.id))
            company = cursor.fetchone()

        clean_recipient = {key: str(value) for key, value in company.items() if key not in avoid_columns}

        clean_recipient['user_id'] = current_user.id
        clean_recipient.pop('email', None)

        recipient_columns = ', '.join(['`{}`'.format(w) for w in list(clean_recipient.keys())])
        recipient_values = ', '.join(['%s']*len(list(clean_recipient.values())))

        with connection.cursor() as cursor:
            sql = "INSERT INTO `recipient` ("+recipient_columns+")"+" VALUES ("+recipient_values+")"
            cursor.execute(sql,(list(clean_recipient.values())))
            connection.commit()

        with connection.cursor() as cursor:
            sql = 'SELECT * FROM `supplier` sp WHERE sp.example = 1 AND sp.user_id = 3 ORDER BY sp.supplier_id ASC'
            cursor.execute(sql)
            suppliers = cursor.fetchall()

        old_supplier_ids = []
        for x in range(len(suppliers)):
            supplier = suppliers[x]
            old_supplier_ids.append(supplier['supplier_id'])

            clean_supplier = {key: str(value) for key, value in supplier.items() if key not in avoid_columns}

            clean_supplier['user_id'] = current_user.id

            supplier_columns = ', '.join(['`{}`'.format(w) for w in list(clean_supplier.keys())])
            supplier_values = ', '.join(['%s']*len(list(clean_supplier.values())))

            with connection.cursor() as cursor:
                sql = "INSERT INTO `supplier` ("+supplier_columns+")"+" VALUES ("+supplier_values+")"
                cursor.execute(sql,(list(clean_supplier.values())))
                connection.commit()

        with connection.cursor() as cursor:
            sql = "SELECT sp.supplier_id FROM `supplier` sp WHERE sp.example = 1 AND sp.user_id = %s ORDER BY sp.supplier_id ASC"
            cursor.execute(sql,(current_user.id))
            new_suppliers = cursor.fetchall()

        new_supplier_ids = []
        for x in range(len(new_suppliers)):
            supplier = new_suppliers[x]
            new_supplier_ids.append(supplier['supplier_id'])

        with connection.cursor() as cursor:
            sql = 'SELECT * FROM `sku_group` sg WHERE sg.example = 1 AND sg.user_id = 3 ORDER BY sg.sku_group_id ASC'
            cursor.execute(sql)
            groups = cursor.fetchall()

        old_sku_group_ids = []

        for x in range(len(groups)):
            group = groups[x]
            old_sku_group_ids.append(group['sku_group_id'])
            with connection.cursor() as cursor:
                sql = 'INSERT INTO `sku_group` (`name`,`example`,`user_id`) VALUES (%s,1,%s)'
                cursor.execute(sql,(group['name'],current_user.id))
                connection.commit()



        with connection.cursor() as cursor:
            sql = "SELECT * FROM sku_group WHERE example = 1 AND user_id = %s ORDER BY sg.sku_group_id ASC"
            cursor.execute(sql,(current_user.id))
            groups = cursor.fetchall()

        new_sku_group_ids = []
        for x in range(len(groups)):
            group = groups[x]
            new_sku_group_ids.append(group['sku_group_id'])



        with connection.cursor() as cursor:
            sql = 'SELECT sk.* FROM `sku` sk LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id WHERE sk.example = 1 AND sp.user_id = 3 ORDER BY sk.sku_id ASC'
            cursor.execute(sql)
            skus = cursor.fetchall()

        old_sku_ids = []
        for x in range(len(skus)):
            sku = skus[x]

            old_sku_ids.append(sku['sku_id'])

            idx = old_supplier_ids.index(sku['supplier_id'])

            supplier_id = new_supplier_ids[idx]

            clean_sku = {key: str(value) for key, value in sku.items() if key not in avoid_columns and value != None}

            clean_sku['supplier_id'] = supplier_id

            sku_columns = ', '.join(['`{}`'.format(w) for w in list(clean_sku.keys())])
            sku_values = ', '.join(['%s']*len(list(clean_sku.values())))

            with connection.cursor() as cursor:
                sql = "INSERT INTO `sku` ("+sku_columns+")"+" VALUES ("+sku_values+")"
                cursor.execute(sql,(list(clean_sku.values())))
                connection.commit()

        with connection.cursor() as cursor:
            sql = 'SELECT sk.sku_id FROM `sku` sk LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id WHERE sk.example = 1 AND sp.user_id = %s ORDER BY sk.sku_id ASC'
            cursor.execute(sql,(current_user.id))
            new_skus = cursor.fetchall()

        new_sku_ids = []
        for x in range(len(new_skus)):
            sku = new_skus[x]
            new_sku_ids.append(sku['sku_id'])


        #pull example groupings
        with connection.cursor() as cursor:
            sql = 'SELECT g.* FROM `grouping` g WHERE g.example = 1 AND g.user_id = 3 ORDER BY g.grouping_id ASC;'
            cursor.execute(sql)
            rows = cursor.fetchall()


        for x in range(len(rows)):
            row = rows[x]
            sku_id = row['sku_id']
            sku_group_id = row['sku_group_id']

            idx_sku_id = old_sku_ids.index(sku_id)
            new_sku_id = new_sku_ids[idx_sku_id]

            idx_sku_group_id = old_sku_group_ids.index(sku_group_id)
            new_group_id = new_sku_group_ids[idx_sku_group_id]

            with connection.cursor() as cursor:
                sql = 'INSERT INTO `grouping` (`sku_id`,`sku_group_id`,`user_id`,`example`) VALUES (%s,%s,%s,%s)'
                cursor.execute(sql,(new_sku_id,new_group_id,current_user.id,1))
                connection.commit()


        with connection.cursor() as cursor:
            sql = 'SELECT o.* FROM `order` o LEFT JOIN `company` c ON o.company_id = c.company_id  LEFT JOIN `image` i ON c.image_id = i.image_id WHERE o.example = 1 AND i.user_id = 3 ORDER BY o.order_id ASC'
            cursor.execute(sql)
            orders = cursor.fetchall()

        old_order_ids = []
        for x in range(len(orders)):
            order = orders[x]
            old_order_ids.append(order['order_id'])
            clean_order = {key: str(value) for key, value in order.items() if key not in avoid_columns}

            today = datetime.today().strftime('%Y-%m-%d')
            mabd = datetime.today()+timedelta(days=14)
            mabd = mabd.strftime('%Y-%m-%d')

            clean_order['order_date'] = today
            clean_order['mabd'] = mabd
            clean_order['ship_to_company'] = 1
            clean_order['access_code'] = access_code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            clean_order['company_id'] = company['company_id']

            order_columns = ', '.join(['`{}`'.format(w) for w in list(clean_order.keys())])
            order_values = ', '.join(['%s']*len(list(clean_order.values())))

            with connection.cursor() as cursor:
                sql = "INSERT INTO `order` ("+order_columns+")"+" VALUES ("+order_values+")"
                cursor.execute(sql,(list(clean_order.values())))
                connection.commit()

        with connection.cursor() as cursor:
            sql = "SELECT o.order_id FROM `order` o LEFT JOIN `company` c ON o.company_id = c.company_id  LEFT JOIN `image` i ON c.image_id = i.image_id WHERE o.example = 1 AND i.user_id = %s ORDER BY o.order_id ASC"
            cursor.execute(sql,(current_user.id))
            new_orders = cursor.fetchall()

        new_order_ids = []
        for x in range(len(new_orders)):
            order = new_orders[x]
            new_order_ids.append(order['order_id'])

        with connection.cursor() as cursor:
            sql = "SELECT ct.* FROM `cart` ct LEFT JOIN `sku` sk ON ct.sku_id = sk.sku_id LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id LEFT JOIN `order` o ON ct.order_id = o.order_id WHERE o.example = 1 AND ct.active = 1 AND sp.user_id = 3 ORDER BY ct.cart_id ASC"
            cursor.execute(sql)
            rows = cursor.fetchall()

        for x in range(len(rows)):
            row = rows[x]
            order_id = new_order_ids[old_order_ids.index(row['order_id'])]
            sku_id = new_sku_ids[old_sku_ids.index(row['sku_id'])]
            cart_dict = {'order_id':order_id,'sku_id':sku_id,'quantity':row['quantity'],'active':1,'cost':row['cost']}
            cart_columns = ', '.join(['`{}`'.format(w) for w in list(cart_dict.keys())])
            cart_values = ', '.join(['%s']*len(list(cart_dict.values())))
            with connection.cursor() as cursor:
                sql = "INSERT INTO `cart` ("+cart_columns+")"+" VALUES ("+cart_values+")"
                cursor.execute(sql,(list(cart_dict.values())))
                connection.commit()
    finally:
        connection.close()

    return 'Great success'


@bp.route('/account', methods=['GET', 'POST'],defaults={"js": "plain",'type':'none'})
@bp.route('/account/<type>', methods=['GET','POST'])
@bp.route("/<any(plain, jquery, fetch):js>")
@login_required
def account(type):
    user = get_user(current_user.id)
    return render_template('account.html',title='Account', user=user)


@bp.route('/load_orders',methods=['POST'])
def load_orders():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """SELECT o.*
            FROM `order` o
            LEFT JOIN `company` c ON o.company_id = c.company_id
            LEFT JOIN `image` i ON c.image_id = i.image_id
            WHERE (i.user_id = %s AND o.active = 1) OR (o.example = 1)
            ORDER BY o.created DESC;"""
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()
            print(result)
            clean_result = []

            for x in range(len(result)):
                dirty = result[x]
                clean = {key: str(value) for key, value in dirty.items()}
                clean_result.append(clean)

            print(clean_result)
            return {'orders':clean_result}
    finally:
        connection.close()


@bp.route('/load_calendar_data',methods=['POST'])
def load_calendar_data():
    start_date = request.json['start_date']
    end_date = request.json['end_date']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT
                o.foreign_id AS `Order ID`
                ,o.order_id AS `order_id`
                ,o.access_code AS `access_code`
                ,o.created AS `Created`
                ,o.mabd AS `MABD`
                ,o.example AS `Example`
                ,y.status AS `Status`
                ,o.tax_rate AS `tax_rate`
                ,l.sku_count AS `SKU Count`
                ,l.line_item AS `Subtotal`
                ,l.supplier_id AS `Supplier ID`
                ,l.supplier_name AS `Supplier`
                ,l.line_item AS `Amount`
                FROM `order` o
                LEFT JOIN (SELECT t.order_id AS `order_id`, MAX(t.user_id) AS `user_id`, MAX(t.supplier_id) AS `supplier_id`, MAX(t.supplier_name) AS `supplier_name`, MAX(t.line_item) AS `line_item`, COUNT(*) AS `sku_count` FROM (SELECT o.order_id AS `order_id` ,sk.sku_id AS `sku_id`, MAX(sp.supplier_id) AS `supplier_id`,MAX(sp.user_id) AS `user_id`, MAX(sp.name) AS `supplier_name`, MAX(sk.cost) AS `cost`, MAX(ct.quantity) AS `quantity`, MAX(sk.cost)*MAX(ct.quantity) AS `line_item` FROM supplier sp LEFT JOIN `sku` sk ON sp.supplier_id = sk.supplier_id LEFT JOIN `cart` ct ON sk.sku_id = ct.sku_id LEFT JOIN `order` o ON ct.order_id = o.order_id WHERE ct.active = 1 GROUP BY o.order_id, sk.sku_id) `t` GROUP BY t.order_id) `l` ON o.order_id = l.order_id
                LEFT JOIN (SELECT status_order_id AS `order_id`,st_b.status AS `status` FROM (SELECT st.order_id AS `status_order_id`,max(st.created) AS `created` FROM `status` st GROUP BY `status_order_id` HAVING `status_order_id` IS NOT NULL) AS x
                INNER JOIN `status` st_b ON x.status_order_id = st_b.order_id AND x.created = st_b.created ) AS y ON o.order_id = y.order_id
                WHERE (o.active = 1 AND l.user_id = %s)
                AND (o.mabd BETWEEN %s AND %s)
                ORDER BY o.created DESC
                LIMIT 50;
            """
            cursor.execute(sql,(current_user.id,start_date,end_date))
            result = cursor.fetchall()

        clean_result = []

        for x in range(len(result)):
            dirty = result[x]
            clean = {key: str(value) for key, value in dirty.items()}
            clean_result.append(clean)

        return json.dumps(clean_result)
    except:
        return json.dumps({'user status':'not logged in'})
    finally:
        connection.close()


@bp.route('/load_dashboard_admin',methods=['POST'])
def load_dashboard_admin():
    print
    connection = getConnection()
    print(current_user.id)
    #first confirm user is dumbledore
    if current_user.id == 3:
        try:

            with connection.cursor() as cursor:
                sql = 'SELECT `demo_id`, `first_name`, `last_name`, `company_name`,`email`,`created` FROM `demo` d WHERE d.demo_status = 0;'
                cursor.execute(sql)
                result = cursor.fetchall()

            clean_result = []

            for x in range(len(result)):
                dirty = result[x]
                clean = {key: str(value) for key, value in dirty.items()}
                clean_result.append(clean)


            open_demos = json.dumps(clean_result);

            return open_demos

        except:
            return 'fail'
    else:
        return 'rejected'

@bp.route('/respond_demo', methods=['POST'])
def respond_demo():
    print('respond demo test')
    demo_status = str(request.json['demo_status'])
    demo_id = str(request.json['demo_id'])
    print('1 Demo status: '+demo_status)
    print('demo id: '+demo_id)
    connection = getConnection()

    if current_user.id != 3:
        return 'rejected'
    try:
        try:
            with connection.cursor() as cursor:
                sql = 'UPDATE `demo` SET `demo_status` = %s, `demo_status_changed_date` = %s WHERE `demo_id` = %s'
                cursor.execute(sql,(demo_status,datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),demo_id))
                print('2 Demo status: '+demo_status)
                connection.commit()
        except:
            return 'fail'

        print('3 Demo status: '+demo_status)
        if demo_status == '1':
            print('test demo status approved')
            print(demo_status)
            with connection.cursor() as cursor:
                sql = 'SELECT demo_code, first_name, email FROM demo WHERE demo_id = %s'
                cursor.execute(sql,(demo_id))
                row = cursor.fetchone()

            send_email(subject='[SpeedyPO] Welcome!',
                sender='support@speedypo.com',
                recipients=row['email'].split(),
                text_body=render_template('welcome.txt',first_name=row['first_name'],demo_code=row['demo_code']),
                html_body=render_template('welcome.html',first_name=row['first_name'],demo_code=row['demo_code']))

        return demo_id
    finally:
        connection.close()

@bp.route('/remove_group_sku',methods=['POST'])
def remove_group_sku():

    sku_id = request.json['sku_id']
    group_id = request.json['group_id']

    connection = getConnection()
    try:
        try:
            with connection.cursor() as cursor:
                sql = 'SELECT `sku_group_id` FROM `grouping` WHERE `user_id` = %s AND `sku_id` = %s AND `sku_group_id` = %s'
                cursor.execute(sql,(current_user.id,sku_id,group_id))
                row = cursor.fetchone()
        except:
            return 'sku fail'
        if row == None:
            return 'sku fail'
        try:
            with connection.cursor() as cursor:
                sql = 'DELETE FROM `grouping` WHERE `user_id` = %s AND `sku_id` = %s AND `sku_group_id` = %s'
                cursor.execute(sql,(current_user.id,sku_id,group_id))
                connection.commit()

            return {'sku_id':sku_id,'group_id':group_id}
        except:
            return 'delete fail'
    finally:
        connection.close()

@bp.route('/load_simple_orders',methods=['POST'])
def load_simple_orders():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT
            o.order_id AS `order_id`
            ,MAX(o.foreign_id) AS `Order ID`
            ,MAX(o.created) AS `Created`
            ,MAX(sp.supplier_id) AS `supplier_id`
            ,MAX(sp.foreign_id) AS `Supplier ID`
            ,MAX(sp.name) AS `Supplier`
            FROM `order` o
            LEFT JOIN `cart` ct ON o.order_id = ct.order_id
            LEFT JOIN `sku` sk ON ct.sku_id = sk.sku_id
            LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            WHERE o.active = 1
            AND sp.user_id = %s
            GROUP BY o.order_id
            ORDER BY o.order_id DESC
            LIMIT 3;
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

        clean_result = []

        for x in range(len(result)):
            d = result[x]
            keys_values = d.items()
            new_d = {key: str(value) for key, value in keys_values}
            clean_result.append(new_d)

        return {'simple_orders':clean_result}
    except:
        return 'simple order sql error'
    finally:
        connection.close()

@bp.route('/load_simple_suppliers',methods=['POST'])
def load_simple_suppliers():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT sp.supplier_id
            ,MAX(sp.name) AS `Supplier`
            ,COUNT(DISTINCT (CASE WHEN sk.active = 1 then sk.sku_id end)) AS `SKU Count`
            ,COUNT(DISTINCT (CASE WHEN o.active = 1 then o.order_id end)) AS `Order Count`
            FROM supplier sp
            LEFT JOIN sku sk ON sp.supplier_id = sk.supplier_id
            LEFT JOIN cart ct ON ct.sku_id = sk.sku_id
            LEFT JOIN `order` o ON ct.order_id = o.order_id
            WHERE sp.active = 1
            AND sp.user_id = %s
            GROUP BY sp.supplier_id
            ORDER BY sp.supplier_id DESC
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

        clean_result = []

        for x in range(len(result)):
            d = result[x]
            keys_values = d.items()
            new_d = {key: str(value) for key, value in keys_values}
            clean_result.append(new_d)

        return {'simple_suppliers':clean_result}
    except:
        return 'simple supplier sql error'
    finally:
        connection.close()

@bp.route('/load_simple_skus',methods=['POST'])
def load_simple_skus():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT sk.sku_id
            ,MAX(sk.foreign_id) AS `SKU ID`
            ,MAX(sk.name) AS `SKU`
            ,MAX(sp.name) AS `Supplier`
            ,MAX(sp.supplier_id) AS `supplier_id`
            ,SUM(if(o.active = 1 AND ct.active = 1,1,0)) AS `Order Count`
            FROM `sku` sk
            LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            LEFT JOIN `cart` ct ON sk.sku_id = ct.sku_id
            LEFT JOIN `order` o ON ct.order_id = o.order_id
            LEFT JOIN `grouping` g ON sk.sku_id = g.sku_id
            LEFT JOIN `sku_group` sg ON g.sku_group_id = sg.sku_group_id
            WHERE sk.active = 1
            AND sp.user_id = %s
            GROUP BY sk.sku_id
            ORDER BY sk.sku_id DESC
            LIMIT 3;
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

        clean_result = []

        for x in range(len(result)):
            d = result[x]
            keys_values = d.items()
            new_d = {key: str(value) for key, value in keys_values}
            clean_result.append(new_d)

        return {'simple_skus':clean_result}
    except:
        return 'simple supplier sql error'
    finally:
        connection.close()




@bp.route('/load_dashboard_orders',methods=['POST'])
def load_dashboard_orders():

    connection = getConnection()

    page = int(request.json['page'])
    per_page = int(request.json['per_page'])
    supplier_id = request.json['supplier_id']
    sku_id = request.json['sku_id']
    container_id = request.json['container_id']


    if supplier_id is not None:
        supplier_condition = 'AND sp.supplier_id = '+supplier_id
    else:
        supplier_condition = ''

    if sku_id is not None:
        sku_condition = 'AND sk.sku_id = '+sku_id
    else:
        sku_condition = ''



    offset = (page-1)*per_page
    limit = per_page

    try:
        with connection.cursor() as cursor:
            sql_1 = """SELECT
            o.order_id AS `order_id`
            ,MAX(o.foreign_id) AS `Order ID`
            ,MAX(o.access_code) AS `access_code`
            ,MAX(o.created) AS `Created`
            ,MAX(o.mabd) AS `MABD`
            ,MAX(o.example) AS `Example`
            ,MAX(o.tax_rate) AS `tax_rate`
            ,MAX(o.status) AS `Status`
            ,MAX(sp.supplier_id) AS `supplier_id`
            ,MAX(sp.foreign_id) AS `Supplier ID`
            ,MAX(sp.name) AS `Supplier`
            ,SUM(if(ct.active = 1,1,0)) AS `SKU Count`
            ,SUM(if(ct.active = 1,ct.cost*ct.quantity,0)) AS `Subtotal`
            FROM `order` o
            LEFT JOIN `cart` ct ON o.order_id = ct.order_id
            LEFT JOIN `sku` sk ON ct.sku_id = sk.sku_id
            LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            WHERE o.active = 1
            AND sp.user_id = %s"""

            sql_2 = supplier_condition

            sql_3 = sku_condition

            sql_4 = """GROUP BY o.order_id
            ORDER BY o.created
            LIMIT %s, %s;"""

            sql = ' '.join([sql_1,sql_2,sql_3,sql_4])
            cursor.execute(sql,(current_user.id,offset,limit))
            result = cursor.fetchall()


        with connection.cursor() as cursor:
            sql = """
                SELECT COUNT(DISTINCT o.order_id) AS order_count
                FROM `order` o
                INNER JOIN cart ct ON o.order_id = ct.order_id
                LEFT JOIN sku sk ON ct.sku_id = sk.sku_id
                LEFT JOIN supplier sp ON sk.supplier_id = sp.supplier_id
                WHERE sp.user_id = %s
                AND o.active = 1
            """
            sql = (' ').join([sql,supplier_condition,sku_condition])
            cursor.execute(sql,(current_user.id))
            order_count = cursor.fetchone()['order_count']

    finally:
        connection.close()

    clean_result = []

    for x in range(len(result)):
        dirty = result[x]

        tax_rate = float(dirty['tax_rate'])/100

        if dirty['Subtotal'] != None:
            subtotal = float(dirty['Subtotal'])
            tax = tax_rate*subtotal
            total = subtotal+tax
        else:
            tax = 0
            total = 0

        additions = {'Tax':tax,'Total':total}

        dirty.update(additions)

        clean = {key: str(value) for key, value in dirty.items()}

        clean_result.append(clean)

    results = {'data':clean_result,
               'count':order_count,
               'per_page':per_page,
               'page':page,
               'container_id':container_id
                };

    return results


@bp.route('/add_group_sku',methods=['POST'])
def add_group_sku():

    group_id = request.json['group_id']

    sku_ids = request.json['sku_ids']

    print({'group_id':group_id,'sku_ids':sku_ids})


    connection = getConnection()

    try:
        for x in range(len(sku_ids)):
            sku_id = sku_ids[x]
            with connection.cursor() as cursor:
                sql = 'INSERT INTO `grouping` (`sku_id`,`sku_group_id`,`user_id`) VALUES (%s,%s,%s)'
                print(sql)
                cursor.execute(sql,(sku_id,group_id,current_user.id))
                connection.commit()
        return {'group_id':group_id,'sku_ids':sku_ids}
    except:
        return 'insert fail'
    finally:
        connection.close()


@bp.route('/load_group_skus',methods=['POST'])
def load_group_skus():
    group_id = request.json['group_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql= """
            SELECT sk.sku_id AS `sku_id`
            ,sk.name AS `SKU`
            ,sp.supplier_id AS `supplier_id`
            ,sp.name AS `Supplier`
            FROM `grouping` g
            LEFT JOIN `sku` sk ON g.sku_id = sk.sku_id
            LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            WHERE g.sku_group_id = %s
            """
            cursor.execute(sql,(group_id))
            result = cursor.fetchall()

        clean_result = []
        for x in range(len(result)):
            d = result[x]
            keys_values = d.items()
            new_d = {key: str(value) for key, value in keys_values}
            clean_result.append(new_d)
        return {'skus':clean_result}
    finally:
        connection.close()



@bp.route('/load_group',methods=['POST'])
def load_group():
    group_id = request.json['group_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """SELECT * FROM `sku_group` WHERE `sku_group_id` = %s LIMIT 1
            """
            cursor.execute(sql,(group_id))
            group = cursor.fetchone()

    finally:
        connection.close()

    clean_group = {key: str(value) for key, value in group.items()}

    return {'group':clean_group}



@bp.route('/delete_group',methods=['POST'])
def delete_group():
    group_id = request.json['group_id']
    print(group_id)
    connection = getConnection()
    try:
        try:
            with connection.cursor() as cursor:
                sql = 'SELECT `sku_group_id` FROM `sku_group` WHERE `sku_group_id` = %s AND `user_id` = %s'
                print(sql)
                cursor.execute(sql,(group_id,current_user.id))
                group = cursor.fetchone()
                print(group)
        except:
            return 'group fail'
        if group == None:
            return 'group fail'
        try:
            with connection.cursor() as cursor:
                sql = 'DELETE FROM `grouping` WHERE `sku_group_id` = %s'
                cursor.execute(sql,(group_id))
                connection.commit()

            with connection.cursor() as cursor:
                sql = 'DELETE FROM `sku_group` WHERE `sku_group_id` = %s'
                cursor.execute(sql,(group_id))
                connection.commit()
            return {'group_id':group_id}
        except:
            return 'delete fail'

    finally:
        connection.close()



@bp.route('/rename_group',methods=['POST'])
def rename_group():
    group_id = request.json['group_id']
    name = request.json['name']
    print(group_id)
    print(name)
    print(current_user.id)
    connection = getConnection()

    try:
        try:
            with connection.cursor() as cursor:
                sql = 'SELECT `sku_group_id` FROM `sku_group` WHERE `sku_group_id` = %s and user_id = %s'
                cursor.execute(sql,(group_id,current_user.id))
                group = cursor.fetchone()
            if group == None:
                return 'group_fail'
        except:
            return 'group_fail'
        try:
            with connection.cursor() as cursor:
                sql = 'UPDATE `sku_group` SET name = %s WHERE `sku_group_id` = %s and user_id = %s'
                print(sql)
                cursor.execute(sql,(name,group_id,current_user.id))
                connection.commit()
        except:
            return 'update_group_fail'
        return {'group_id':group_id,'name':name}
    finally:
        connection.close()



@bp.route('/load_simple_groups',methods=['POST'])
def load_simple_groups():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT * FROM sku_group WHERE user_id = %s'
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()
    finally:
        connection.close()

    clean_result = []

    for x in range(len(result)):
        d = result[x]
        keys_values = d.items()
        new_d = {key: str(value) for key, value in keys_values}
        clean_result.append(new_d)

    return {'simple_groups':clean_result}



@bp.route('/load_dashboard_groups',methods=['POST'])
def load_dashboard_groups():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT * FROM sku_group WHERE user_id = %s'
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()
    finally:
        connection.close()

    clean_result = []

    for x in range(len(result)):
        d = result[x]
        keys_values = d.items()
        new_d = {key: str(value) for key, value in keys_values}
        clean_result.append(new_d)

    return {'group_result':clean_result}






@bp.route('/load_dashboard_skus',methods=['POST'])
def load_dashboard_skus():

    page = int(request.json['page'])
    per_page = int(request.json['per_page'])
    supplier_id = request.json['supplier_id']
    container_id = request.json['container_id']
    group_id = request.json['group_id']


    offset = (page-1)*per_page
    limit = per_page

    if supplier_id is not None:
        supplier_condition = 'AND sp.supplier_id = '+supplier_id
    else:
        supplier_condition = ''

    if group_id is not None:
        group_condition = 'AND sg.sku_group_id = '+group_id
    else:
        group_condition = ''


    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql_1 = """
            SELECT sk.sku_id
            ,MAX(sk.foreign_id) AS `SKU ID`
            ,MAX(sk.name) AS `SKU`
            ,MAX(sp.name) AS `Supplier`
            ,MAX(sp.supplier_id) AS `supplier_id`
            ,MAX(sk.pack_qty) AS `Pack Qty`
            ,MAX(sk.cost) AS `Cost`
            ,MAX(sk.example) AS `Example`
            ,SUM(if(o.active = 1 AND ct.active = 1,1,0)) AS `Order Count`
            FROM `sku` sk
            LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            LEFT JOIN `cart` ct ON sk.sku_id = ct.sku_id
            LEFT JOIN `order` o ON ct.order_id = o.order_id
            LEFT JOIN `grouping` g ON sk.sku_id = g.sku_id
            LEFT JOIN `sku_group` sg ON g.sku_group_id = sg.sku_group_id
            WHERE sk.active = 1
            AND sp.user_id = %s
            """

            sql_2 = supplier_condition

            sql_3 = group_condition

            sql_4 = """
            GROUP BY sk.sku_id
            ORDER BY sk.created DESC
            LIMIT %s, %s;
            """

            sql = ' '.join([sql_1,sql_2,sql_3,sql_4])
            cursor.execute(sql,(current_user.id,offset,limit))
            result = cursor.fetchall()

        with connection.cursor() as cursor:
            sql = """
            SELECT count(sk.sku_id) AS sku_count
            FROM `sku` sk
            INNER JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            WHERE sk.active = 1
            AND sp.user_id = %s
            """
            sql = (' ').join([sql,supplier_condition])
            cursor.execute(sql,(current_user.id))
            sku_count = cursor.fetchone()['sku_count']

    finally:
        connection.close()

    clean_result = []

    for x in range(len(result)):
        d = result[x]
        keys_values = d.items()
        new_d = {key: str(value) for key, value in keys_values}
        clean_result.append(new_d)


    results = {'data':clean_result,
       'count':sku_count,
       'per_page':per_page,
       'page':page,
       'container_id':container_id
        };

    return results

@bp.route('/update_status',methods=['POST'])
def update_status():
    order_id = request.json['order_id']
    status = request.json['status']
    connection = getConnection()
    print('update status test')
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT `order_id`,`status`,`delivered_date` FROM `order` WHERE order_id = %s'
            cursor.execute(sql,(order_id))
            order = cursor.fetchone()

        with connection.cursor() as cursor:
            sql = 'UPDATE `order` SET status = %s WHERE order_id = %s'
            cursor.execute(sql,(status,order_id))
            connection.commit()


        if order['delivered_date'] == None and status == '3':

            date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

            with connection.cursor() as cursor:
                sql = 'UPDATE `order` SET `delivered_date` = %s WHERE order_id = %s'
                cursor.execute(sql,(date,order_id))
                connection.commit()

        return order_id
    finally:
        connection.close()

@bp.route('/load_order',methods=['POST'])
def load_order():

    order_id = request.json['order_id']
    print('Order ID: '+str(order_id))
    connection = getConnection()

    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT
                o.foreign_id AS `foreign_id`
                ,o.order_id AS `order_id`
                ,o.access_code AS `access_code`
                ,o.created AS `created`
                ,o.mabd AS `mabd`
                ,o.delivered_date AS `delivered_date`
                ,o.shipping_method AS `shipping_method`
                ,o.shipping_terms AS `shipping_terms`
                ,o.tax_rate AS `tax_rate`
                ,o.order_date AS `order_date`
                ,o.example AS `example`
                ,sk.sku_count AS `sku_count`
                ,c.company_id AS `company_id`
                ,c.name AS `company_name`
                ,c.street AS `company_street`
                ,c.city AS `company_city`
                ,c.state AS `company_state`
                ,c.zip AS `company_zip`
                ,c.country AS `company_country`
                ,c.email AS `company_email`
                ,c.phone AS `company_phone`
                ,r.recipient_id AS `recipient_id`
                ,r.name AS `recipient_name`
                ,r.street AS `recipient_street`
                ,r.city AS `recipient_city`
                ,r.state AS `recipient_state`
                ,r.zip AS `recipient_zip`
                ,r.country AS `recipient_country`
                ,r.phone AS `recipient_phone`
                ,o.ship_to_company AS `ship_to_company`
                ,i.image_id AS `image_id`
                ,i.image_name AS `image_name`
                ,i.extension AS `extension`
                ,o.order_notes AS `notes`
                ,o.active AS `active`
                ,sp.supplier_id AS `supplier_id`
                ,sp.foreign_id AS `supplier_foreign_id`
                ,sp.name AS `supplier_name`
                ,sp.street AS `supplier_street`
                ,sp.city AS `supplier_city`
                ,sp.state AS `supplier_state`
                ,sp.zip AS `supplier_zip`
                ,sp.country AS `supplier_country`
                ,sp.email AS `supplier_email`
                ,sp.phone AS `supplier_phone`
                ,o.status AS `status`
                FROM `order` o
                INNER JOIN company c ON o.company_id = c.company_id
                LEFT JOIN image i ON c.image_id = i.image_id
                LEFT JOIN `recipient` r on o.recipient_id = r.recipient_id
                LEFT JOIN (SELECT x.order_id AS `order_id`, sp.* FROM (SELECT ct.order_id AS `order_id`, max(sp.supplier_id) AS `supplier_id` FROM `cart` ct LEFT JOIN `sku` sk ON ct.sku_id = sk.sku_id  LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id GROUP BY ct.order_id) x LEFT JOIN `supplier` sp ON x.supplier_id = sp.supplier_id)  sp ON sp.order_id = o.order_id
                LEFT JOIN (SELECT ct.order_id AS order_id, COUNT(ct.sku_id) AS sku_count FROM cart ct WHERE ct.active = 1 GROUP BY ct.order_id) sk ON o.order_id = sk.order_id
                WHERE o.order_id = %s;
            """
            cursor.execute(sql,(order_id))
            order = cursor.fetchone()
            print(order)

            #image_path = os.path.join('static/uploads/',order_id+'.jpg')
        #change dates to better format
        #print('Order: '+str(order))
        order['order_date'] = order['order_date'].strftime('%-m-%d-%y')
        order['created'] = order['created'].strftime('%-m-%d-%y')
        order['mabd'] = order['mabd'].strftime('%-m-%d-%y')
        if order['delivered_date'] != None:
            order['delivered_date'] = order['delivered_date'].strftime('%-m-%d-%y')

        keys_values = order.items()

        order = {key: str(value) for key, value in keys_values}

        #sku grain
        with connection.cursor() as cursor:
            sql = """SELECT * FROM `cart` ct LEFT JOIN `sku` sk ON ct.sku_id = sk.sku_id WHERE ct.order_id = %s AND ct.active = 1
            """
            print('sql test')
            print(sql)
            cursor.execute(sql,order_id)
            skus = cursor.fetchall()
        print('skus test')
        print(skus)
        clean_skus = []

        for x in range(len(skus)):
            dirty = skus[x]
            clean = {key: str(value) for key, value in dirty.items()}
            clean_skus.append(clean)

        #calculate top line using sku data
        line_items = []
        for x in range(len(clean_skus)):
            sku = clean_skus[x]
            cost = float(sku['cost'])
            quantity = float(sku['quantity'])
            line_item = cost*quantity
            line_items.append(line_item)

        subtotal = sum(line_items)
        tax_rate = float(order['tax_rate'])/100
        tax = subtotal*tax_rate
        total = subtotal+tax

        top_line = {'subtotal':str(subtotal),'tax':str(tax),'total':str(total)}

        order.update(top_line)

    finally:
        connection.close()

    return {'order':order,'skus':clean_skus}

@bp.route('/load_recipient',methods=['POST'])
def load_recipient():
    recipient_id = request.json['recipient_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT * FROM `recipient` WHERE `recipient_id` = %s LIMIT 1
            """
            cursor.execute(sql,(recipient_id))
            row = cursor.fetchone()
        return {'recipient_result':row}
    finally:
        connection.close()






@bp.route('/load_supplier',methods=['POST'])
def load_supplier():
    supplier_id = request.json['supplier_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT * FROM `supplier` WHERE `supplier_id` = %s LIMIT 1
            """
            cursor.execute(sql,(supplier_id))
            row = cursor.fetchone()

        return {'supplier_result':row}
    finally:
        connection.close()

@bp.route('/load_supplier_page',methods=['POST'])
def load_supplier_page():
    supplier_id = request.json['supplier_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT
            sp.*
            ,COUNT(DISTINCT (CASE WHEN sk.active = 1 then sk.sku_id end)) AS `SKU Count`
            ,COUNT(DISTINCT (CASE WHEN o.active = 1 then o.order_id end)) AS `Order Count`
            ,COUNT(DISTINCT (CASE WHEN o.active = 1 AND o.status = 3 then o.order_id end)) AS `Delivered Count`
            ,COUNT(DISTINCT (CASE WHEN o.active = 1 AND o.status = 2 then o.order_id end)) AS `Shipped Count`
            FROM `supplier` sp
            LEFT JOIN sku sk ON sp.supplier_id = sk.supplier_id
            LEFT JOIN cart ct ON ct.sku_id = sk.sku_id
            LEFT JOIN `order` o ON ct.order_id = o.order_id
            WHERE sp.supplier_id = %s
            LIMIT 1
            """
            cursor.execute(sql,(supplier_id))
            row = cursor.fetchone()

        return {'supplier_result':row}
    finally:
        connection.close()




@bp.route('/load_sku_page',methods=['POST'])
def load_sku_page():
    sku_id = request.json['sku_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT
            sk.*
            ,sp.name AS `Supplier`
            ,COUNT(DISTINCT (CASE WHEN sk.active = 1 then sk.sku_id end)) AS `SKU Count`
            ,COUNT(DISTINCT (CASE WHEN o.active = 1 then o.order_id end)) AS `Order Count`
            ,COUNT(DISTINCT (CASE WHEN o.active = 1 AND o.status = 3 then o.order_id end)) AS `Delivered Count`
            ,COUNT(DISTINCT (CASE WHEN o.active = 1 AND o.status = 2 then o.order_id end)) AS `Shipped Count`
            FROM sku sk
            LEFT JOIN supplier sp ON sk.supplier_id = sp.supplier_id
            LEFT JOIN cart ct ON ct.sku_id = sk.sku_id
            LEFT JOIN `order` o ON ct.order_id = o.order_id
            WHERE sk.sku_id = %s
            LIMIT 1
            """
            cursor.execute(sql,(sku_id))
            row = cursor.fetchone()

            sku = {key: str(value) for key, value in row.items()}

        return {'sku_result':sku}
    finally:
        connection.close()

@bp.route('/load_sku',methods=['POST'])
def load_sku():
    sku_id = request.json['sku_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT * FROM `sku` WHERE `sku_id` = %s LIMIT 1
            """
            cursor.execute(sql,(sku_id))
            row = cursor.fetchone()

            keys_values = row.items()
            new_d = {key: str(value) for key, value in keys_values}


        return {'sku_result':new_d}
    finally:
        connection.close()



@bp.route('/load_dashboard_active_orders',methods=['POST'])
def load_dashboard_active_orders():
    container_id = request.json['container_id']

    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """SELECT
                    ao.active_order_id AS active_order_id
                    ,sp.supplier_id AS supplier_id
                    ,sp.foreign_id AS `Supplier ID`
                    ,sp.name AS `Supplier`
                    FROM `active_order` ao
                    LEFT JOIN `supplier` sp ON ao.supplier_id = sp.supplier_id
                    WHERE ao.user_id = %s
                    GROUP BY 1,2,3,4
                    ORDER BY ao.active_order_id ASC"""
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

        orders = []
        for x in range(len(result)):
            d = result[x]
            keys_values = d.items()
            new_d = {key: str(value) for key, value in keys_values}
            orders.append(new_d)

        with connection.cursor() as cursor:
            sql = """SELECT ao.active_order_id AS active_order_id
                    ,sk.sku_id AS sku_id
                    ,sk.foreign_id AS `SKU ID`
                    ,sk.name AS `SKU`
                    FROM `active_order` ao
                    LEFT JOIN `active_cart` ac ON ao.active_order_id = ac.active_order_id
                    LEFT JOIN sku sk ON ac.sku_id = sk.sku_id
                    LEFT JOIN supplier sp ON sk.supplier_id = sp.supplier_id
                    AND sp.user_id = %s
                    GROUP BY 1,2,3,4
                    ORDER BY ao.active_order_id ASC"""
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

            skus = []
            for x in range(len(result)):
                d = result[x]
                keys_values = d.items()
                new_d = {key: str(value) for key, value in keys_values}
                skus.append(new_d)

        result = {'orders':orders,'skus':skus,'container_id':container_id}
    finally:
        connection.close()
    return result



@bp.route('/load_dashboard_suppliers',methods=['POST'])
def load_dashboard_suppliers():


    page = int(request.json['page'])
    per_page = int(request.json['per_page'])
    container_id = request.json['container_id']
    offset = (page-1)*per_page
    limit = per_page


    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT sp.supplier_id
            ,MAX(sp.name) AS `Supplier`
            ,MAX(sp.email) AS `Email`
            ,MAX(sp.foreign_id) AS `Supplier ID`
            ,MAX(sp.example) AS `Example`
            ,COUNT(DISTINCT (CASE WHEN sk.active = 1 then sk.sku_id end)) AS `SKU Count`
            ,COUNT(DISTINCT (CASE WHEN o.active = 1 then o.order_id end)) AS `Order Count`
            FROM supplier sp
            LEFT JOIN sku sk ON sp.supplier_id = sk.supplier_id
            LEFT JOIN cart ct ON ct.sku_id = sk.sku_id
            LEFT JOIN `order` o ON ct.order_id = o.order_id
            WHERE sp.active = 1
            AND sp.user_id = %s
            GROUP BY sp.supplier_id
            ORDER BY sp.created DESC
            LIMIT %s, %s;
            """
            cursor.execute(sql,(current_user.id,offset,limit))
            result = cursor.fetchall()

        with connection.cursor() as cursor:
            sql = """
            SELECT count(sp.supplier_id) AS supplier_count
            FROM `supplier` sp
            WHERE sp.user_id = %s
            AND sp.active = 1
            """
            cursor.execute(sql,(current_user.id))
            supplier_count = cursor.fetchone()['supplier_count']

    finally:
        connection.close()

    clean_result = []

    for x in range(len(result)):
        d = result[x]
        keys_values = d.items()
        new_d = {key: str(value) for key, value in keys_values}
        clean_result.append(new_d)

    results = {'data':clean_result,
               'count':supplier_count,
               'per_page':per_page,
               'page':page,
               'container_id':container_id
                };

    return results




@bp.route('/load_dashboard_company',methods=['POST'])
def load_dashboard_company():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT *
            FROM company c
            LEFT JOIN image i ON c.image_id = i.image_id
            LEFT JOIN `order` o ON c.company_id = o.company_id
            WHERE i.user_id = %s
            AND c.active = 1
            ORDER BY c.created DESC
            LIMIT 1
            """

            cursor.execute(sql,(current_user.id))
            result = cursor.fetchone()
            keys_values = result.items()
            clean_result = {key: str(value) for key, value in keys_values}

        return clean_result
    finally:
        connection.close()


@bp.route('/load_dashboard_recipients',methods=['POST'])
def load_dashboard_recipients():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT r.*
            FROM recipient r
            LEFT JOIN `order` o ON r.recipient_id = o.recipient_id
            WHERE r.user_id = %s AND r.active = 1
            GROUP BY r.recipient_id
            ORDER BY r.modified DESC
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

            clean_result = []

            for x in range(len(result)):
                d = result[x]
                keys_values = d.items()
                new_d = {key: str(value) for key, value in keys_values}
                clean_result.append(new_d)

        return {'recipient_result':clean_result}
    finally:
        connection.close()




@bp.route('/active_suppliers', methods=['POST'])
def active_suppliers():
    supplier_id = request.json['supplier_id']

    if supplier_id is not None:
        supplier_condition = 'AND sp.supplier_id = '+supplier_id
    else:
        supplier_condition = ''
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql_1 = """
            SELECT sp.name AS `Supplier Name`
            ,sp.foreign_id AS `Supplier ID`
            ,sp.supplier_id AS `supplier_id`
            FROM `user` u
            LEFT JOIN `supplier` sp ON u.user_id = sp.user_id
            LEFT JOIN (SELECT MAX(o.example) AS `example`, sk.supplier_id AS `supplier_id` FROM cart ct LEFT JOIN (SELECT o.order_id AS `order_id`, o.example AS `example` FROM `order` o WHERE o.example = 1) o ON ct.order_id = o.order_id LEFT JOIN sku sk ON ct.sku_id = sk.sku_id WHERE o.example = 1 GROUP BY sk.supplier_id ) o ON sp.supplier_id = o.supplier_id
            WHERE sp.active = 1
            AND u.user_id = %s"""

            sql_2 = supplier_condition

            sql_3 = """ORDER BY sp.created DESC
            LIMIT 50"""

            sql = ' '.join([sql_1,sql_2,sql_3])
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

    finally:
        connection.close()
    return {'result':result}

@bp.route('/active_recipients', methods=['POST'])
def active_recipients():
    connection = getConnection()

    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT r.*
            FROM recipient r
            LEFT JOIN `order` o ON r.recipient_id = o.recipient_id
            WHERE (user_id = %s AND r.active = 1)
            GROUP BY r.recipient_id
            ORDER BY r.modified DESC
            LIMIT 5
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

    finally:
        connection.close()
    return {'result':result}

@bp.route('/active_skus', methods=['POST'])
def active_skus():
    sku_id = request.json['sku_id']

    if sku_id is not None:
        sku_condition = 'AND sk.sku_id = '+sku_id
    else:
        sku_condition = ''

    supplier_id = request.json['supplier_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql_1 = """
            SELECT sk.*
            FROM `sku` sk
            LEFT JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            WHERE sp.supplier_id = %s
            AND sk.active = 1
            """

            sql_2 = sku_condition

            sql_3 = """ORDER BY sk.created DESC
            LIMIT 50"""

            sql = ' '.join([sql_1,sql_2,sql_3])
            cursor.execute(sql,(supplier_id))
            result = cursor.fetchall()

        clean_result = []

        for x in range(len(result)):
            dirty = result[x]
            clean = {key: str(value) for key, value in dirty.items()}
            clean_result.append(clean)

    finally:
        connection.close()
    return {'result':clean_result}




@bp.route('/active_company', methods=['POST'])
def active_company():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT c.*, i.*
            FROM image i
            LEFT JOIN company c ON i.image_id = c.image_id
            WHERE i.user_id = %s
            ORDER BY c.created DESC
            LIMIT 1
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchall()

    finally:
        connection.close()
    return {'result':result}



@bp.route('/order_count',methods=['POST'])
def order_count():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT count(o.order_id) AS order_count
            FROM `order` o
            LEFT JOIN company c ON o.company_id = c.company_id
            LEFT JOIN image i ON c.image_id = i.image_id
            WHERE i.user_id = %s
            AND o.active = 1
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchone()
            result = result['order_count']
            if result == None:
                return 'none'
            else:
                return result
    finally:
        connection.close()

@bp.route('/supplier_count',methods=['POST'])
def supplier_count():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT count(sp.supplier_id) AS supplier_count
            FROM `supplier` sp
            WHERE sp.user_id = %s
            AND sp.active = 1
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchone()
            result = result['supplier_count']
            if result == None:
                return 'none'
            else:
                return result
    finally:
        connection.close()

@bp.route('/sku_count',methods=['POST'])
def sku_count():
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """
            SELECT count(sk.sku_id) AS sku_count
            FROM `sku` sk
            INNER JOIN `supplier` sp ON sk.supplier_id = sp.supplier_id
            WHERE sk.active = 1
            AND sp.user_id = %s
            """
            cursor.execute(sql,(current_user.id))
            result = cursor.fetchone()
            result = result['sku_count']
            if result == None:
                return 'none'
            else:
                return result
    finally:
        connection.close()



@bp.route('/remove_recipient',methods=['POST'])
def remove_recipient():
    recipient_id = request.json['recipient_id']
    connection = getConnection()

    try:
        with connection.cursor() as cursor:
            sql = """UPDATE `recipient`
            SET `active` = 0
            WHERE `recipient_id` = %s"""
            cursor.execute(sql,(recipient_id))
            connection.commit()
    finally:
        connection.close()
        return 'Great success'


@bp.route("/remove_supplier", methods=['POST'])
def remove_supplier():
    supplier_id = request.json['supplier_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """UPDATE `supplier`
            SET `active` = 0
            WHERE `supplier_id` = %s"""
            cursor.execute(sql,(supplier_id))
            connection.commit()
            return "Great success"
    finally:
        connection.close()


@bp.route("/remove_sku", methods=['POST'])
def remove_sku():
    sku_id = request.json['sku_id']
    connection = getConnection()
    try:
        with connection.cursor() as cursor:
            sql = """UPDATE `sku`
            SET `active` = 0
            WHERE `sku_id` = %s"""
            cursor.execute(sql,(sku_id))
            connection.commit()
            return "Great success"
    finally:
        connection.close()


@bp.route("/remove_order", methods=['POST'])
def remove_order():
    order_id = request.json['order_id'];
    connection = getConnection()
    try:

        with connection.cursor() as cursor:
            sql = """UPDATE `order`
            SET `active` = 0
            WHERE `order_id` = %s
            """
            cursor.execute(sql,(order_id))
            connection.commit()
            return 'pass'
    except:
        return 'fail'
    finally:
        connection.close()


#poker splitter app
@bp.route('/poker_splitter', methods=['GET','POST'], defaults={"js": "plain"})
@bp.route("/<any(plain, jquery, fetch):js>")
def poker_splitter(js):
    return render_template('poker_splitter.html',js=js)

@bp.route("/split", methods=["POST"])
def split():

    name_array = request.json['name']
    buy_in_array = request.json['buy_in']
    buy_out_array = request.json['buy_out']

    result = poker_split(name_array=name_array,buy_in_array=buy_in_array,buy_out_array=buy_out_array)

    result = "---".join(result)

    return str(result)


@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(basedir, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
