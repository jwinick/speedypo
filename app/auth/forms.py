from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
from app.models import User, load_user
import pymysql.cursors
from app.myconnutils import getConnection


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(),
                                           EqualTo('password')])
    admin_code = PasswordField('Admin Code',validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        connection = getConnection()
        try:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM `user` WHERE `user_name` = %s"
                cursor.execute(sql,(username.data))
                user = cursor.fetchone()
        finally:
            connection.close()
        if user is not None:
            raise ValidationError('Please use a different username.')




    def validate_email(self, email):

        connection = getConnection()
        try:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM `user` WHERE `user_email` = %s"
                cursor.execute(sql,(email.data))
                user = cursor.fetchone()
        finally:
            connection.close()
        if user is not None:
            raise ValidationError('Please use a different email address.')


# class ResetPasswordRequestForm(FlaskForm):
#     email = StringField('Email'), validators=[DataRequired(), Email()]
#     submit = SubmitField('Request Password Reset')


# class ResetPasswordForm(FlaskForm):
#     password = PasswordField('Password'), validators=[DataRequired()]
#     password2 = PasswordField(
#         'Repeat Password'), validators=[DataRequired(),
#                                            EqualTo('password')]
#     submit = SubmitField(_l('Request Password Reset'))
