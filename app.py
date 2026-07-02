import os
import sys
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from config import Config
from models import db, User, Movie, Review
from forms import RegisterForm, LoginForm, MovieForm, ReviewForm
from forms import RoleChangeForm
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import date
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from functools import wraps

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.init_app(app)

    # For sqlite local development, ensure new columns are added when code
    # introduces small schema changes. This helper will add the `last_login`
    # column to `users` if it's missing. It only runs for sqlite URIs.
    def _ensure_sqlite_columns():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
        if not uri.startswith('sqlite'):
            return

        with app.app_context():
            try:
                # Use raw connection to run PRAGMA and ALTER TABLE safely
                conn = db.engine.raw_connection()
                cur = conn.cursor()
                cur.execute("PRAGMA table_info('users')")
                cols = [r[1] for r in cur.fetchall()]
                if 'last_login' not in cols:
                    cur.execute("ALTER TABLE users ADD COLUMN last_login DATETIME")
                    conn.commit()
                
                # Check movies table for created_at column
                cur.execute("PRAGMA table_info('movies')")
                movie_cols = [r[1] for r in cur.fetchall()]
                if 'created_at' not in movie_cols:
                    cur.execute("ALTER TABLE movies ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                    conn.commit()
                
                cur.close()
                conn.close()
            except Exception:
                # If anything goes wrong here, don't block app start — the app
                # will still work, but last_login will remain unavailable.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    cur.close()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass

    _ensure_sqlite_columns()

    # Initialize login manager
    login_manager = LoginManager(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Utility functions
    def is_18_or_above(dob):
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age >= 18

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

    # Routes
    @app.route('/')
    def index():
        movies = Movie.query.all()
        avg_ratings = {}
        for m in movies:
            revs = m.reviews
            if revs:
                avg = sum([r.rating for r in revs]) / len(revs)
            else:
                avg = None
            avg_ratings[m.id] = avg
        return render_template('index.html', movies=movies, avg_ratings=avg_ratings)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = RegisterForm()
        if form.validate_on_submit():
            if not is_18_or_above(form.dob.data):
                flash('You must be at least 18 years old to register.', 'danger')
                return render_template('register.html', form=form)
            hashed = generate_password_hash(form.password.data)
            user = User(
                name=form.name.data,
                email=form.email.data,
                password=hashed,
                dob=form.dob.data,
                role='user'
            )
            db.session.add(user)
            try:
                db.session.commit()
                flash('Registration successful. Please login.', 'success')
                return redirect(url_for('login'))
            except IntegrityError:
                db.session.rollback()
                flash('Email already registered.', 'danger')
        return render_template('register.html', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user and check_password_hash(user.password, form.password.data):
                login_user(user)
                # record last login time
                try:
                    user.last_login = datetime.utcnow()
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                flash('Logged in successfully.', 'success')
                return redirect(url_for('index'))
            flash('Invalid credentials.', 'danger')
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out.', 'info')
        return redirect(url_for('index'))

    # Admin decorator
    def admin_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != 'admin':
                flash('Admin access required.', 'danger')
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return wrapper

    # Admin dashboard
    @app.route('/admin')
    @login_required
    @admin_required
    def admin_dashboard():
        movies = Movie.query.all()
        users = User.query.all()
        return render_template('admin_dashboard.html', movies=movies, users=users)

    @app.route('/admin/users')
    @login_required
    @admin_required
    def admin_users():
        q = request.args.get('q', '')
        page = request.args.get('page', 1, type=int)
        query = User.query
        if q:
            ilike_q = f"%{q}%"
            query = query.filter((User.name.ilike(ilike_q)) | (User.email.ilike(ilike_q)))
        pagination = query.order_by(User.id).paginate(page=page, per_page=10, error_out=False)
        users = pagination.items
        role_form = RoleChangeForm()
        return render_template('admin_users.html', users=users, pagination=pagination, q=q, role_form=role_form)

    @app.route('/admin/add_movie', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def add_movie():
        form = MovieForm()
        if form.validate_on_submit():
            f = form.poster.data
            filename = secure_filename(f.filename)
            if not allowed_file(filename):
                flash('File type not allowed.', 'danger')
                return render_template('add_movie.html', form=form)
            # ensure unique filename
            base, ext = os.path.splitext(filename)
            i = 1
            final = filename
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], final)):
                final = f"{base}_{i}{ext}"
                i += 1
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], final))
            # Check for existing movie with same title
            existing_movie = Movie.query.filter(Movie.title.ilike(form.title.data)).first()
            if existing_movie:
                flash('A movie with this title already exists in the database.', 'danger')
                return render_template('add_movie.html', form=form)

            # Check for existing movie with same title
            existing_movie = Movie.query.filter(Movie.title.ilike(form.title.data)).first()
            if existing_movie:
                flash('A movie with this title already exists in the database.', 'danger')
                return render_template('add_movie.html', form=form)

            movie = Movie(
                title=form.title.data,
                poster=final,
                description=form.description.data,
                added_by=current_user.id
            )
            try:
                db.session.add(movie)
                db.session.commit()
                flash('Movie added successfully.', 'success')
                return redirect(url_for('admin_dashboard'))
            except IntegrityError:
                db.session.rollback()
                flash('A movie with this title already exists.', 'danger')
                return render_template('add_movie.html', form=form)
        return render_template('add_movie.html', form=form)

    @app.route('/admin/edit_movie/<int:movie_id>', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def edit_movie(movie_id):
        movie = Movie.query.get_or_404(movie_id)
        form = MovieForm()
        if form.validate_on_submit():
            # Update title and description
            movie.title = form.title.data or movie.title
            movie.description = form.description.data or movie.description

            # If a new poster was uploaded, save and replace
            f = form.poster.data
            if f:
                filename = secure_filename(f.filename)
                if not allowed_file(filename):
                    flash('File type not allowed.', 'danger')
                    return render_template('add_movie.html', form=form, movie=movie)
                base, ext = os.path.splitext(filename)
                i = 1
                final = filename
                while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], final)):
                    final = f"{base}_{i}{ext}"
                    i += 1
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], final))
                # remove old poster file if exists and not the placeholder
                try:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], movie.poster)
                    if os.path.exists(old_path) and movie.poster != 'placeholder.png':
                        os.remove(old_path)
                except Exception:
                    pass
                movie.poster = final

            db.session.commit()
            flash('Movie updated successfully.', 'success')
            return redirect(url_for('admin_dashboard'))

        # Pre-populate form fields for GET
        if request.method == 'GET':
            form.title.data = movie.title
            form.description.data = movie.description

        return render_template('add_movie.html', form=form, movie=movie)

    @app.route('/admin/delete_movie/<int:movie_id>', methods=['POST'])
    @login_required
    @admin_required
    def delete_movie(movie_id):
        movie = Movie.query.get_or_404(movie_id)
        # delete poster file if exists and not placeholder
        try:
            poster_path = os.path.join(app.config['UPLOAD_FOLDER'], movie.poster)
            if os.path.exists(poster_path) and movie.poster != 'placeholder.png':
                os.remove(poster_path)
        except Exception:
            pass
        db.session.delete(movie)
        db.session.commit()
        flash('Movie deleted.', 'info')
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/promote_user/<int:user_id>', methods=['POST'])
    @login_required
    @admin_required
    def promote_user(user_id):
        user = User.query.get(user_id)
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('admin_dashboard'))

        if user.role == 'admin':
            flash('User is already an admin.', 'info')
            return redirect(url_for('admin_dashboard'))

        user.role = 'admin'
        db.session.commit()
        flash(f'User {user.email} promoted to admin.', 'success')
        return redirect(url_for('admin_users'))

    @app.route('/admin/demote_user/<int:user_id>', methods=['POST'])
    @login_required
    @admin_required
    def demote_user(user_id):
        user = User.query.get(user_id)
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('admin_users'))

        if user.role != 'admin':
            flash('User is not an admin.', 'info')
            return redirect(url_for('admin_users'))

        # Safety: ensure at least one admin remains
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot demote the last admin.', 'danger')
            return redirect(url_for('admin_users'))

        user.role = 'user'
        db.session.commit()
        flash(f'User {user.email} demoted to user.', 'success')
        return redirect(url_for('admin_users'))

    @app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
    @login_required
    @admin_required
    def delete_user(user_id):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Only admins can delete users.', 'danger')
            return redirect(url_for('login'))

        user = User.query.get_or_404(user_id)
        
        # Prevent deleting admin users
        if user.role == 'admin':
            flash('Admin users cannot be deleted.', 'danger')
            return redirect(url_for('admin_users'))
            
        # Get count of reviews to be deleted
        review_count = Review.query.filter_by(user_id=user.id).count()
        
        try:
            # Delete related reviews first
            if review_count > 0:
                Review.query.filter_by(user_id=user.id).delete()
            
            # Delete the user
            db.session.delete(user)
            db.session.commit()
            
            msg = f'Deleted user {user.email}'
            if review_count > 0:
                msg += f' and their {review_count} reviews'
            flash(msg + '.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Error deleting user. Please try again.', 'danger')
            
        return redirect(url_for('admin_users'))

    @app.route('/movie/<int:movie_id>', methods=['GET', 'POST'])
    def movie_detail(movie_id):
        movie = Movie.query.get_or_404(movie_id)
        form = ReviewForm()
        banned_keywords = ['ending', 'dies', 'death', 'kill', 'murder', 'spoiler']

        if form.validate_on_submit():
            if not current_user.is_authenticated:
                flash('Login required to post a review.', 'danger')
                return redirect(url_for('login'))
            existing = Review.query.filter_by(movie_id=movie.id, user_id=current_user.id).first()
            if existing:
                flash('You have already reviewed this movie.', 'warning')
                return redirect(url_for('movie_detail', movie_id=movie.id))
            text_lower = (form.review_text.data or '').lower()
            for kw in banned_keywords:
                if kw in text_lower:
                    flash('Please avoid spoilers in your review.', 'danger')
                    return render_template('movie_detail.html', movie=movie, form=form)
            review = Review(
                movie_id=movie.id,
                user_id=current_user.id,
                recommend=bool(int(form.recommend.data)),
                rating=int(form.rating.data),
                review_text=form.review_text.data
            )
            db.session.add(review)
            db.session.commit()
            flash('Review submitted successfully.', 'success')
            return redirect(url_for('movie_detail', movie_id=movie.id))

        reviews = Review.query.filter_by(movie_id=movie.id).order_by(Review.created_at.desc()).all()
        return render_template('movie_detail.html', movie=movie, form=form, reviews=reviews)

    @app.route('/posters/<filename>')
    def poster_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    return app


# Run the app
if __name__ == '__main__':
    # Create the app and attempt to create DB tables. If the configured
    # SQLALCHEMY_DATABASE_URI points to a MySQL server that isn't reachable
    # we'll fall back to a local sqlite DB automatically once per process.
    app = create_app()
    with app.app_context():
        # Only auto-create tables automatically when using sqlite. If the
        # configured DB is a remote MySQL instance that's down we avoid
        # attempting to create tables (which would raise a connection error).
        uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        if uri.startswith('sqlite'):
            db.create_all()
        else:
            print('NOTE: not running db.create_all() because configured DB is not sqlite.\n'
                  'If you want tables created automatically, either start your MySQL server\n'
                  'or set DATABASE_URL to a sqlite path for local development.')

    app.run(debug=True)
