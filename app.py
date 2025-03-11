import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from forms import UploadPhotoForm, RegistrationForm, LoginForm, FolderForm
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from datetime import datetime

# ініціалізація додатку
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Функція для перевірки дозволених розширень файлів
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# AWS S3 настройки
AWS_ACCESS_KEY_ID = 'AKIAY6QVY4LJ4SRR5THN'
AWS_SECRET_ACCESS_KEY = '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'
AWS_BUCKET_NAME = 'testbucketpian'
AWS_REGION = 'eu-north-1'

# Ініціалізація бази даних та менеджера входу
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Моделі для користувачів, папок і фото
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    folders = db.relationship('Folder', backref='user', lazy=True)

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subfolders = db.relationship('Folder')

    photos = db.relationship('Photo', backref='folder', lazy=True)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=False)
    filepath = db.Column(db.String(300), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ініціалізація бази даних
with app.app_context():
    db.create_all()

# Завантаження користувача
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Головна сторінка
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    return render_template('home_page.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Хешуємо пароль перед збереженням
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Login failed. Check username and/or password', 'danger')
    return render_template('login.html', form=form)

# Сторінка профілю користувача
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = FolderForm()  # Створення форми для папки
    if form.validate_on_submit():
        folder_name = form.folder_name.data
        new_folder = Folder(name=folder_name, user_id=current_user.id)
        db.session.add(new_folder)
        db.session.commit()
        flash(f'Folder "{folder_name}" created!', 'success')
    folders = Folder.query.filter_by(user_id=current_user.id, parent_id=None).all()  # Отримуємо папки
    return render_template('profile.html', form=form, folders=folders)

# Вихід користувача
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out!', 'info')
    return redirect(url_for('home'))

# Функція для завантаження фото на S3
def upload_file_to_s3(file):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    # Перетворюємо ім'я файлу на безпечне
    filename = secure_filename(file.filename)
    print(f"Uploading file: {filename}")  # Для відлагодження

    # Завантажуємо файл на S3
    try:
        s3_client.upload_fileobj(
            file,
            AWS_BUCKET_NAME,
            filename,
            ExtraArgs={'ACL': 'public-read'}
        )
        # Формуємо URL для доступу до файлу
        file_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
        print(f"File uploaded successfully, URL: {file_url}")  # Для відлагодження
        return file_url
    except Exception as e:
        print(f"Error uploading file to S3: {e}")  # Для відлагодження
        return None

@app.route('/upload_photo/<int:folder_id>', methods=['POST', 'GET'])
@login_required
def upload_photo(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    
    if folder.user_id != current_user.id:
        flash('You do not have permission to upload photos to this folder.', 'danger')
        return redirect(url_for('profile'))
    
    form = UploadPhotoForm()  # Створюємо форму для завантаження фото
    
    if request.method == 'POST' and form.validate_on_submit():
        file = form.photo.data
        if file:
            print(f"File received: {file.filename}")  # Для відлагодження
            # Завантажуємо фото на S3
            file_url = upload_file_to_s3(file)
            
            if file_url:
                new_photo = Photo(filename=file.filename, filepath=file_url, folder_id=folder.id)
                db.session.add(new_photo)
                db.session.commit()
                flash('Photo uploaded successfully!', 'success')
                return redirect(url_for('view_folder', folder_id=folder.id))
            else:
                flash('Error uploading photo', 'danger')
    
    return render_template('upload_photo.html', folder=folder, form=form)

@app.route('/folder/<int:folder_id>', methods=['GET', 'POST'])
@login_required
def view_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    
    if folder.user_id != current_user.id:
        flash('You do not have permission to view this folder.', 'danger')
        return redirect(url_for('profile'))

    # Форма для створення підпапки
    form = FolderForm()

    # Форма для завантаження фото
    upload_form = UploadPhotoForm()

    if form.validate_on_submit():
        folder_name = form.folder_name.data
        new_folder = Folder(name=folder_name, user_id=current_user.id, parent_id=folder.id)
        db.session.add(new_folder)
        db.session.commit()
        flash(f'Subfolder "{folder_name}" created!', 'success')
        return redirect(url_for('view_folder', folder_id=folder.id))

    if upload_form.validate_on_submit():
        file = upload_form.photo.data
        if file and allowed_file(file.filename):
            file_url = upload_file_to_s3(file)
            if file_url:
                new_photo = Photo(filename=file.filename, filepath=file_url, folder_id=folder.id)
                db.session.add(new_photo)
                db.session.commit()
                flash('Photo uploaded successfully!', 'success')
                return redirect(url_for('view_folder', folder_id=folder.id))
            else:
                flash('Error uploading photo to S3', 'danger')

    subfolders = Folder.query.filter_by(parent_id=folder.id).all()  # Отримуємо підпапки
    photos = Photo.query.filter_by(folder_id=folder.id).all()  # Отримуємо фото в поточній папці

    return render_template('view_folder.html', folder=folder, form=form, upload_form=upload_form, subfolders=subfolders, photos=photos)


@app.route('/delete_folder/<int:folder_id>', methods=['POST'])
@login_required
def delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        flash('You do not have permission to delete this folder.', 'danger')
        return redirect(url_for('profile'))
    
    # Видалення фото в папці
    for photo in folder.photos:
        db.session.delete(photo)
    
    # Видалення підпапок
    for subfolder in folder.subfolders:
        db.session.delete(subfolder)

    db.session.delete(folder)
    db.session.commit()
    
    flash(f'Folder "{folder.name}" deleted successfully!', 'success')
    return redirect(url_for('profile'))



if __name__ == '__main__':
    app.run(debug=True)
