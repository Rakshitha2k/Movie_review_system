from app import create_app
from models import db, User

TARGET_EMAIL = 'ranjit12@gmail.com'  # the user found in the DB earlier

app = create_app()
with app.app_context():
    u = User.query.filter_by(email=TARGET_EMAIL).first()
    if not u:
        print('User not found:', TARGET_EMAIL)
    else:
        if u.role == 'admin':
            print('User is already admin:', u.email)
        else:
            u.role = 'admin'
            db.session.commit()
            print('Promoted user to admin:', u.email)
