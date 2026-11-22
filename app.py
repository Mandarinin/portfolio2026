"""portfolio — личный сайт-визитка на Flask."""
from datetime import timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import re
import secrets

from flask import Flask, abort, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import selectinload
from werkzeug.security import check_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'site.db'

db = SQLAlchemy()


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    stack = db.Column(db.Text, nullable=False)
    visual_type = db.Column(db.String(20), nullable=False, default='text')
    visual_text = db.Column(db.String(120))
    image_filename = db.Column(db.String(160))
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    links = db.relationship(
        'ProjectLink', back_populates='project', cascade='all, delete-orphan',
        order_by='ProjectLink.sort_order',
    )

    @property
    def stack_items(self):
        return [item.strip() for item in self.stack.split('|') if item.strip()]


class ProjectLink(db.Model):
    __tablename__ = 'project_links'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    label = db.Column(db.String(110), nullable=False)
    url = db.Column(db.String(600), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    project = db.relationship('Project', back_populates='links')


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.current_timestamp()
    )


class AdminUser(db.Model):
    """Один администратор: хранится только хеш пароля, не сам пароль."""
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    password_hash = db.Column(db.String(255), nullable=False)


def validate_contact_form(name, email, message):
    errors = {}
    if not 2 <= len(name) <= 80:
        errors['name'] = 'Укажите имя от 2 до 80 символов.'
    if not email or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        errors['email'] = 'Укажите корректный email.'
    if not 10 <= len(message) <= 2000:
        errors['message'] = 'Сообщение должно содержать от 10 до 2000 символов.'
    return errors


def get_secret_key():
    """Стабильный локальный ключ сессии; при публикации задаётся через окружение."""
    from_environment = os.environ.get('FLASK_SECRET_KEY')
    if from_environment:
        return from_environment

    key_file = BASE_DIR / '.secret_key'
    try:
        return key_file.read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        new_key = secrets.token_hex(32)
        try:
            with key_file.open('x', encoding='utf-8') as file:
                file.write(new_key)
            key_file.chmod(0o600)
            return new_key
        except FileExistsError:
            return key_file.read_text(encoding='utf-8').strip()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    token = session.get('_admin_csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_admin_csrf'] = token
    return token


def verify_admin_csrf():
    expected = session.get('_admin_csrf', '')
    submitted = request.form.get('csrf_token', '')
    if not expected or not submitted or not secrets.compare_digest(expected, submitted):
        abort(400, description='Недействительный запрос. Обновите страницу и повторите действие.')


def project_form_data(project=None):
    if project:
        return {
            'title': project.title,
            'description': project.description,
            'stack': ', '.join(project.stack_items),
            'visual_type': project.visual_type,
            'visual_text': project.visual_text or '',
            'image_filename': project.image_filename or '',
            'sort_order': project.sort_order,
            'links': [{'label': link.label, 'url': link.url} for link in project.links],
        }
    return {
        'title': '', 'description': '', 'stack': '',
        'visual_type': 'text', 'visual_text': '', 'image_filename': '',
        'sort_order': 0, 'links': [{'label': '', 'url': ''}],
    }


def read_project_form(form):
    labels = form.getlist('link_label')
    urls = form.getlist('link_url')
    links = [
        {'label': labels[index].strip() if index < len(labels) else '',
         'url': urls[index].strip() if index < len(urls) else ''}
        for index in range(max(len(labels), len(urls)))
    ]
    return {
        'title': form.get('title', '').strip(),
        'description': form.get('description', '').strip(),
        'stack': form.get('stack', '').strip(),
        'visual_type': form.get('visual_type', 'text'),
        'visual_text': form.get('visual_text', '').strip(),
        'image_filename': form.get('image_filename', '').strip(),
        'sort_order': form.get('sort_order', '0').strip(),
        'links': links or [{'label': '', 'url': ''}],
    }


def valid_project_link(url):
    if url.startswith('/static/docs/'):
        # Ссылки на отчёты проекта, без перехода в другие каталоги.
        filename = url[len('/static/docs/'):]
        return (
            bool(filename) and filename == Path(filename).name
            and (BASE_DIR / 'static' / 'docs' / filename).is_file()
        )
    if any(character.isspace() for character in url):
        return False
    try:
        parsed = urlsplit(url)
        return parsed.scheme in ('https', 'http') and bool(parsed.hostname)
    except ValueError:
        return False


def validate_project_form(data):
    errors = {}
    if not 2 <= len(data['title']) <= 160:
        errors['title'] = 'Название: от 2 до 160 символов.'
    if not 10 <= len(data['description']) <= 3000:
        errors['description'] = 'Описание: от 10 до 3000 символов.'

    skills = [part.strip() for part in re.split(r'[,|\n]+', data['stack']) if part.strip()]
    if not skills or len(skills) > 30 or any(len(skill) > 70 for skill in skills):
        errors['stack'] = 'Укажите от 1 до 30 технологий, разделённых запятыми.'

    if data['visual_type'] not in ('text', 'image'):
        errors['visual_type'] = 'Выберите тип изображения.'
    if len(data['visual_text']) > 120:
        errors['visual_text'] = 'Не больше 120 символов.'
    if data['visual_type'] == 'image':
        filename = data['image_filename']
        valid_name = (
            bool(filename) and len(filename) <= 160
            and filename == Path(filename).name
            and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))
            and (BASE_DIR / 'static' / 'images' / filename).is_file()
        )
        if not valid_name:
            errors['image_filename'] = 'Укажите имя существующего файла из static/images.'
    try:
        order = int(data['sort_order'])
        if not 0 <= order <= 9999:
            raise ValueError
    except (ValueError, TypeError):
        errors['sort_order'] = 'Порядок: целое число от 0 до 9999.'

    filled_links = [link for link in data['links'] if link['label'] or link['url']]
    if not 1 <= len(filled_links) <= 10:
        errors['links'] = 'У проекта должна быть хотя бы одна ссылка (не больше 10).'
    elif any(
        not 1 <= len(link['label']) <= 110 or len(link['url']) > 600
        or not valid_project_link(link['url'])
        for link in filled_links
    ):
        errors['links'] = 'Заполните название и корректный адрес для каждой ссылки.'
    return errors


def save_project(project, data):
    project.title = data['title']
    project.description = data['description']
    project.stack = '|'.join(
        part.strip() for part in re.split(r'[,|\n]+', data['stack']) if part.strip()
    )
    project.visual_type = data['visual_type']
    project.visual_text = data['visual_text'] or None
    project.image_filename = data['image_filename'] if data['visual_type'] == 'image' else None
    project.sort_order = int(data['sort_order'])
    filled_links = [link for link in data['links'] if link['label'] or link['url']]
    project.links = [
        ProjectLink(label=link['label'], url=link['url'], sort_order=index)
        for index, link in enumerate(filled_links, start=1)
    ]
    db.session.add(project)
    db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=get_secret_key(),
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{DB_PATH.as_posix()}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    db.init_app(app)
    app.jinja_env.globals['csrf_token'] = csrf_token

    with app.app_context():
        db.create_all()  # Новая таблица admin_users; существующие данные не стираются.
        if not db.session.query(Project.id).first():
            records = json.loads((BASE_DIR / 'data' / 'initial_projects.json').read_text(encoding='utf-8'))
            for item in records:
                links_data = item.pop('links', [])
                project = Project(**item)
                project.links = [ProjectLink(**link) for link in links_data]
                db.session.add(project)
            db.session.commit()

    @app.after_request
    def admin_no_cache(response):
        if request.path.startswith('/admin'):
            response.headers['Cache-Control'] = 'no-store, private'
            response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/projects')
    def projects():
        items = db.session.query(Project).options(selectinload(Project.links)).order_by(
            Project.sort_order, Project.id
        ).all()
        return render_template('projects.html', projects=items)

    @app.route('/contacts', methods=['GET', 'POST'])
    def contacts():
        form_data = {'name': '', 'email': '', 'message': ''}
        errors = {}
        if request.method == 'POST':
            form_data = {
                'name': request.form.get('name', '').strip(),
                'email': request.form.get('email', '').strip(),
                'message': request.form.get('message', '').strip(),
            }
            errors = validate_contact_form(**form_data)
            if not errors:
                db.session.add(ContactMessage(**form_data))
                db.session.commit()
                return redirect(url_for('contacts', sent=1), code=303)
        return render_template(
            'contacts.html', form_data=form_data, errors=errors,
            sent=request.args.get('sent') == '1' and request.method == 'GET',
        ), (400 if errors else 200)

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if session.get('admin_id'):
            return redirect(url_for('admin_dashboard'))
        error = None
        configured = db.session.query(AdminUser.id).first() is not None
        if request.method == 'POST':
            verify_admin_csrf()
            admin = db.session.query(AdminUser).first()
            password = request.form.get('password', '')
            if admin and check_password_hash(admin.password_hash, password):
                session.clear()
                session.permanent = True
                session['admin_id'] = admin.id
                return redirect(url_for('admin_dashboard'), code=303)
            error = 'Неверный пароль.' if configured else 'Сначала задайте пароль администратора.'
        return render_template('admin_login.html', error=error, configured=configured), (400 if error else 200)

    @app.post('/admin/logout')
    @admin_required
    def admin_logout():
        verify_admin_csrf()
        session.clear()
        return redirect(url_for('index'), code=303)

    @app.get('/admin')
    @admin_required
    def admin_dashboard():
        items = db.session.query(Project).order_by(Project.sort_order, Project.id).all()
        return render_template('admin_dashboard.html', projects=items)

    @app.get('/admin/messages')
    @admin_required
    def admin_messages():
        messages = db.session.query(ContactMessage).order_by(
            ContactMessage.created_at.desc(), ContactMessage.id.desc()
        ).all()
        return render_template('admin_messages.html', messages=messages)

    @app.route('/admin/projects/new', methods=['GET', 'POST'])
    @admin_required
    def admin_project_new():
        data = project_form_data()
        next_order = db.session.query(db.func.max(Project.sort_order)).scalar() or 0
        data['sort_order'] = next_order + 1
        errors = {}
        if request.method == 'POST':
            verify_admin_csrf()
            data = read_project_form(request.form)
            errors = validate_project_form(data)
            if not errors:
                save_project(Project(), data)
                return redirect(url_for('admin_dashboard'), code=303)
        return render_template(
            'admin_project_form.html', data=data, errors=errors,
            editing=False, project_id=None,
        ), (400 if errors else 200)

    @app.route('/admin/projects/<int:project_id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_project_edit(project_id):
        project = db.get_or_404(Project, project_id)
        data = project_form_data(project)
        errors = {}
        if request.method == 'POST':
            verify_admin_csrf()
            data = read_project_form(request.form)
            errors = validate_project_form(data)
            if not errors:
                save_project(project, data)
                return redirect(url_for('admin_dashboard'), code=303)
        return render_template(
            'admin_project_form.html', data=data, errors=errors,
            editing=True, project_id=project_id,
        ), (400 if errors else 200)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
