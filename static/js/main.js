// Мобильное меню.
const menuToggle = document.querySelector('.menu-toggle');
const menu = document.querySelector('#site-menu');

if (menuToggle && menu) {
  menuToggle.addEventListener('click', () => {
    const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
    menuToggle.setAttribute('aria-expanded', String(!isExpanded));
    menuToggle.setAttribute('aria-label', isExpanded ? 'Открыть меню' : 'Закрыть меню');
    menu.classList.toggle('is-open', !isExpanded);
  });

  menu.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.setAttribute('aria-label', 'Открыть меню');
      menu.classList.remove('is-open');
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.setAttribute('aria-label', 'Открыть меню');
      menu.classList.remove('is-open');
    }
  });
}


// Проверка формы контактов на стороне браузера.
const contactForm = document.querySelector('#contact-form');
if (contactForm) {
  const fields = {
    name: contactForm.querySelector('[name="name"]'),
    email: contactForm.querySelector('[name="email"]'),
    message: contactForm.querySelector('[name="message"]'),
  };
  const showError = (key, text) => {
    const field = fields[key];
    const error = contactForm.querySelector(`#${key}-error`);
    error.textContent = text;
    if (text) field.setAttribute('aria-invalid', 'true');
    else field.removeAttribute('aria-invalid');
  };
  Object.entries(fields).forEach(([key, field]) => {
    field.addEventListener('input', () => showError(key, ''));
  });
  contactForm.addEventListener('submit', (event) => {
    const name = fields.name.value.trim();
    const email = fields.email.value.trim();
    const message = fields.message.value.trim();
    const checks = {
      name: name.length >= 2 && name.length <= 80 ? '' : 'Укажите имя от 2 до 80 символов.',
      email: email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? '' : 'Укажите корректный email.',
      message: message.length >= 10 && message.length <= 2000 ? '' : 'Сообщение должно содержать от 10 до 2000 символов.',
    };
    Object.entries(checks).forEach(([key, text]) => showError(key, text));
    const invalid = Object.keys(checks).find(key => checks[key]);
    if (invalid) {
      event.preventDefault();
      fields[invalid].focus();
    }
  });
}

// В административной форме редактирования проекта можно добавлять ссылки.
const projectForm = document.querySelector('#project-form');
if (projectForm) {
  const visualSelect = projectForm.querySelector('#project-visual-type');
  const updateVisualFields = () => {
    projectForm.querySelectorAll('[data-visual-field]').forEach((field) => {
      field.hidden = field.dataset.visualField !== visualSelect.value;
    });
  };
  visualSelect.addEventListener('change', updateVisualFields);
  updateVisualFields();

  const list = projectForm.querySelector('#project-links-list');
  projectForm.querySelector('#add-project-link').addEventListener('click', () => {
    if (list.querySelectorAll('.admin-link-row').length >= 10) return;
    const row = document.createElement('div');
    row.className = 'admin-link-row';
    row.innerHTML = '<div class="form-field"><label>Название ссылки</label><input name="link_label" type="text" maxlength="110" placeholder="Отчёт о проекте"></div>' +
      '<div class="form-field"><label>Адрес ссылки</label><input name="link_url" type="text" maxlength="600" placeholder="https://... или /static/docs/..."></div>' +
      '<button class="admin-remove-link" type="button" data-remove-link>Убрать</button>';
    list.appendChild(row);
  });
  list.addEventListener('click', (event) => {
    if (event.target.closest('[data-remove-link]')) {
      event.target.closest('.admin-link-row').remove();
    }
  });
}
