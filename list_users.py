from app import create_app
from models import User

app = create_app()
with app.app_context():
    users = User.query.all()
    print('Users in DB:', len(users))
    for u in users:
        print('-', u.id, u.name, u.email, 'role=', u.role)
