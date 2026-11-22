"""Однократно задать или сменить пароль админ-панели portfolio."""
from getpass import getpass

from werkzeug.security import generate_password_hash
from app import AdminUser, app, db


def main():
    with app.app_context():
        existing = db.session.query(AdminUser).first()
        if existing:
            print('Изменение пароля администратора portfolio.')
        else:
            print('Первоначальная настройка администратора portfolio.')

        password = getpass('Новый пароль (минимум 8 символов): ')
        if len(password) < 8:
            print('Пароль слишком короткий. Нужны минимум 8 символов.')
            return
        confirmation = getpass('Повторите пароль: ')
        if password != confirmation:
            print('Пароли не совпадают. Попробуйте снова.')
            return

        admin = existing or AdminUser()
        admin.password_hash = generate_password_hash(password)
        db.session.add(admin)
        db.session.commit()
        print('Пароль сохранён. Вход — по нажатию на имя в шапке сайта.')


if __name__ == '__main__':
    main()
