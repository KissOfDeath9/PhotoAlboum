from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, EqualTo
from wtforms import FileField, SubmitField
from flask_wtf.file import FileRequired, FileAllowed

class UploadPhotoForm(FlaskForm):
    photo = FileField('Upload Photo', validators=[
        FileRequired(), 
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')
    ])
    submit = SubmitField('Upload')



class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=150)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Register')
    
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Login')
    
class FolderForm(FlaskForm):
    folder_name = StringField('Folder Name', validators=[InputRequired()])
    submit = SubmitField('Create Folder')
