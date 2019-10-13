from configparser import ConfigParser
from os.path import expanduser
from flask import Flask, flash, render_template, redirect, request, url_for
from flask_login import current_user, login_required, login_user, logout_user, LoginManager
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired

from accupassword import Checker

_defaults = {
    'database': {
        'host': 'localhost',
        'password': 'NotTheActualPassword'
    }
}

class Config(ConfigParser):
    def __init__(self, configfile=None):
        super().__init__()
        self.read_dict(_defaults)
        if configfile:
            with open(configfile) as f:
                self.read_file(f)
        else:
            self.read([expanduser('~/.accu.cfg'),
                     '/etc/accu/website.cfg'])

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wjMB4SQxSY_3nuvYmpYyWg'

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

cfg = Config()
password_checker = Checker(cfg['database']['host'], cfg['database']['password'])

class Member:
    def __init__(self, name=None):
        self.name = name

    def is_authenticated(self):
        return self.name is not None

    def is_active(self):
        return self.is_authenticated()

    def is_anonymous(self):
        return not self.is_authenticated()

    def get_id(self):
        return self.name

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

@login_manager.user_loader
def load_user(user_id):
    return Member(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect('/')
    form = LoginForm()
    if form.validate_on_submit():
        if password_checker.member(form.username.data, form.password.data):
            user = Member(form.username.data)
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect('/journal/cvu')
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))
    return render_template('login.html', title='Sign In', form=form)

@app.route("/logout", methods=["GET"])
def logout():
    logout_user()
    return redirect('/')

@app.route('/journal/<path:page_path>')
@login_required
def render_static(page_path):
    return render_template(page_path)

if __name__ == '__main__':
    app.run()
