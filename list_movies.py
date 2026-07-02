from app import create_app
from models import Movie

app = create_app()
with app.app_context():
    try:
        movies = Movie.query.all()
        print('Movies in DB:', len(movies))
        for m in movies:
            print('-', m.id, m.title, m.poster)
    except Exception as e:
        print('Error querying movies:', e)
