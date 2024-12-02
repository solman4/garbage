# init_db.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Tạo app Flask mới
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Khởi tạo database
db = SQLAlchemy(app)

# Định nghĩa model User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

def init_database():
    with app.app_context():
        db.create_all()
        print("Database initialized!")

if __name__ == "__main__":
    init_database()