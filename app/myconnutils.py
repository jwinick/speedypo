import pymysql.cursors
from pathlib import Path

test_location = str(Path(__file__).resolve().parents[3])



if(test_location == '/Users/jacobwinick/Dropbox'):
# Function return a connection.

    def getConnection():
        connection = pymysql.connect(host='**********',
                                 user='**********',
                                 password='**********',
                                 db='db',
                                 charset='utf8mb4',
                                 port=3306,
                                 cursorclass=pymysql.cursors.DictCursor)
        return connection

    # def getConnection():

    #     # You can change the connection arguments.
    #     connection = pymysql.connect(host='localhost',
    #                              user='super',
    #                              password='testing',
    #                              db='db',
    #                              charset='utf8mb4',
    #                              cursorclass=pymysql.cursors.DictCursor)
    #     return connection

else:
    def getConnection():

        # You can change the connection arguments.
        connection = pymysql.connect(host='localhost',
                                 user='**********',
                                 password='**********',
                                 db='db',
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
        return connection
