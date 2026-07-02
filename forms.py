from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, DateField, IntegerField, TextAreaField, RadioField, SelectField
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.validators import DataRequired, Email, EqualTo, Length

from wtforms import StringField, PasswordField, SubmitField, BooleanField, DateField, IntegerField, TextAreaField, RadioField, SelectField

from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange
from flask_wtf.file import FileAllowed, FileRequired

class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(1,100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    dob = DateField('Date of Birth (YYYY-MM-DD)', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class MovieForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(1,200)])
    # Poster is optional on edit; allow images only
    poster = FileField('Poster', validators=[FileAllowed(['jpg','png','jpeg','gif'], 'Images only!')])
    description = TextAreaField('Description', validators=[Length(max=1000)])
    submit = SubmitField('Add Movie')

class ReviewForm(FlaskForm):
    recommend = RadioField('Do you recommend?', choices=[('1','Recommend'),('0','Not Recommend')], validators=[DataRequired()])
    from wtforms import RadioField, TextAreaField, SelectField, SubmitField
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired

class ReviewForm(FlaskForm):
    rating = RadioField(
        'Rating',
        choices=[
            ('1', '⭐'),
            ('2', '⭐⭐'),
            ('3', '⭐⭐⭐'),
            ('4', '⭐⭐⭐⭐'),
            ('5', '⭐⭐⭐⭐⭐')
        ],
        validators=[DataRequired()]
    )
    review_text = TextAreaField('Review', validators=[DataRequired()])
    recommend = SelectField('Recommend', choices=[('1','Yes'), ('0','No')])
    submit = SubmitField('Submit')

    review_text = TextAreaField('Spoiler-free Review (max 1000 chars)', validators=[Length(max=1000)])
    submit = SubmitField('Submit Review')


class RoleChangeForm(FlaskForm):
    """Simple form to provide CSRF protection for promote/demote actions."""
    submit = SubmitField('Change')
