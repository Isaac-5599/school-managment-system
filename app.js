'use strict';

/* ============================================================= state */

const state = { user: null, ref: null, route: 'dashboard', examSheet: null };
const ui = {
  term: 'First Term',
  year: '2025/2026',
  students: { page: 1, q: '', class_id: '', sort: 'admission_no' },
  teachers: { page: 1, q: '' },
  attendance: { class_id: '', date: new Date().toISOString().slice(0, 10) },
  fees: { class_id: '', term: 'First Term' },
  reports: { tab: 'results', class_id: '' },
};

/* ============================================================= dom */

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = String(value);
      else if (key.startsWith('on') && typeof value === 'function') {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else node.setAttribute(key, String(value));
    }
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

const appRoot = () => document.getElementById('app');

function money(value) {
  const number = Number(value || 0);
  return '₦' + number.toLocaleString('en-NG', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function initials(name) {
  return String(name || '?').split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase();
}

function badge(status, label) {
  return el('span', { class: 'badge ' + status, text: label === undefined ? String(status).replace(/_/g, ' ') : label });
}

function pctBar(pct, klass) {
  const width = Math.max(0, Math.min(100, Number(pct) || 0));
  const tone = klass || (width >= 70 ? 'good' : width >= 50 ? '' : width >= 40 ? 'warn' : 'bad');
  const fill = el('div', { class: 'bar-fill' + (tone ? ' ' + tone : '') });
  fill.style.width = width + '%';
  return el('div', { class: 'bar-track' }, fill);
}

/* ============================================================= api */

async function api(path, opts) {
  const options = { method: (opts && opts.method) || 'GET', credentials: 'same-origin', headers: {} };
  if (opts && opts.body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(opts.body);
  }
  const response = await fetch(path, options);
  let payload = null;
  try { payload = await response.json(); } catch (err) { payload = null; }

  if (response.status === 401 && state.user) {
    state.user = null;
    renderLogin();
    throw new Error((payload && payload.error) || 'Your session expired. Please sign in again.');
  }
  if (!response.ok) throw new Error((payload && payload.error) || 'Request failed (' + response.status + ')');
  return payload;
}

/* ============================================================= feedback */

function toast(message, kind) {
  const node = el('div', { class: 'toast ' + (kind || ''), text: message });
  document.getElementById('toast-root').appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

function modal({ title, body, actions, wide }) {
  const root = document.getElementById('modal-root');
  const close = () => { clear(root); document.removeEventListener('keydown', onKey); };
  const onKey = event => { if (event.key === 'Escape') close(); };

  const box = el('div', { class: 'modal' + (wide ? ' wide' : ''), role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
    el('div', { class: 'modal-head' },
      el('h2', { class: 'grow', text: title }),
      el('button', { class: 'btn ghost sm', text: 'Close', onclick: close, 'aria-label': 'Close dialog' })
    ),
    el('div', { class: 'modal-body' }, body),
    actions && el('div', { class: 'modal-foot' }, actions)
  );

  const backdrop = el('div', { class: 'modal-backdrop', onclick: event => { if (event.target === backdrop) close(); } }, box);
  clear(root).appendChild(backdrop);
  document.addEventListener('keydown', onKey);
  const focusable = box.querySelector('input, select, button');
  if (focusable) focusable.focus();
  return close;
}

function confirmDialog(message, confirmLabel) {
  return new Promise(resolve => {
    const close = modal({
      title: 'Please confirm',
      body: el('p', { text: message }),
      actions: [
        el('button', { class: 'btn', text: 'Cancel', onclick: () => { close(); resolve(false); } }),
        el('button', { class: 'btn danger', text: confirmLabel || 'Delete', onclick: () => { close(); resolve(true); } })
      ]
    });
  });
}

/* ============================================================= forms */

function buildField(spec, values) {
  const current = values && spec.name in values ? values[spec.name]
    : (spec.default === undefined ? '' : spec.default);
  let control;
  if (spec.type === 'select') {
    control = el('select', { name: spec.name });
    if (!spec.required && !spec.noBlank) control.appendChild(el('option', { value: '', text: '— none —' }));
    for (const option of spec.options || []) {
      const node = el('option', { value: String(option.value), text: option.label });
      if (String(current) === String(option.value)) node.selected = true;
      control.appendChild(node);
    }
  } else {
    control = el('input', {
      type: spec.type || 'text',
      name: spec.name,
      value: current === null || current === undefined ? '' : String(current),
      placeholder: spec.placeholder || '',
      step: spec.step, min: spec.min, max: spec.max
    });
  }
  return el('div', { class: 'field' + (spec.span === 'full' ? ' full' : '') },
    el('label', { text: spec.label + (spec.required ? ' *' : '') }),
    control,
    spec.help && el('span', { class: 'help', text: spec.help })
  );
}

async function openForm({ title, fields, values, wide, submitLabel, intro, onSubmit }) {
  return new Promise(resolve => {
    const form = el('form', { class: 'form-grid' }, fields.map(f => buildField(f, values)));
    const errorBox = el('div');
    let done = false;

    const close = modal({
      title, wide,
      body: [intro ? el('p', { class: 'notice-box', text: intro }) : null, errorBox, form],
      actions: [
        el('button', { class: 'btn', text: 'Cancel', onclick: () => { if (!done) { done = true; close(); resolve(null); } } }),
        el('button', {
          class: 'btn primary', text: submitLabel || 'Save',
          onclick: async event => {
            if (done) return;
            event.preventDefault();
            const button = event.currentTarget;
            const payload = {};
            for (const spec of fields) {
              const control = form.elements[spec.name];
              if (!control) continue;
              const raw = control.value;
              if (spec.required && (raw === '' || raw === null)) {
                errorBox.replaceChildren(el('div', { class: 'error-box', text: spec.label + ' is required.' }));
                control.focus();
                return;
              }
              if (raw === '' && !spec.required) continue;
              payload[spec.name] = spec.type === 'number' ? Number(raw) : raw;
            }
            errorBox.replaceChildren();
            button.disabled = true;
            try {
              const result = await onSubmit(payload);
              done = true;
              close();
              resolve(result);
            } catch (err) {
              button.disabled = false;
              errorBox.replaceChildren(el('div', { class: 'error-box', text: err.message }));
            }
          }
        })
      ]
    });
  });
}

/* ============================================================= tables */

function dataTable(columns, rows, emptyText) {
  if (!rows || !rows.length) return el('div', { class: 'empty', text: emptyText || 'No records found.' });
  const head = el('tr', {}, columns.map(c => el('th', { class: c.className || '', text: c.label })));
  const body = rows.map(row =>
    el('tr', {}, columns.map(c => el('td', { class: c.className || '' }, c.render ? c.render(row) : String(row[c.key] ?? ''))))
  );
  return el('div', { class: 'table-scroll' }, el('table', {}, el('thead', {}, head), el('tbody', {}, body)));
}

function pager(meta, onGo) {
  const pages = Math.max(1, Math.ceil(meta.total / meta.page_size));
  return el('div', { class: 'pager' },
    el('span', { text: 'Showing page ' + meta.page + ' of ' + pages + ' — ' + meta.total + ' record(s)' }),
    el('span', { class: 'spacer' }),
    el('button', { class: 'btn sm', text: 'Previous', disabled: meta.page <= 1, onclick: () => onGo(meta.page - 1) }),
    el('button', { class: 'btn sm', text: 'Next', disabled: meta.page >= pages, onclick: () => onGo(meta.page + 1) })
  );
}

function card(title, actions, bodyNodes, flush) {
  return el('div', { class: 'card' },
    el('div', { class: 'card-head' },
      el('h2', { class: 'grow', text: title }),
      actions && el('div', { class: 'toolbar' }, actions)
    ),
    el('div', { class: 'card-body' + (flush ? ' flush' : '') }, bodyNodes)
  );
}

function stat(label, value, hint, accent) {
  return el('div', { class: 'stat' + (accent ? ' accent-' + accent : '') },
    el('div', { class: 'label', text: label }),
    el('div', { class: 'value', text: String(value) }),
    hint && el('div', { class: 'hint', text: hint })
  );
}

/* ============================================================= login */

const DEMO_LOGINS = [
  { role: 'Administrator', username: 'admin', password: 'Admin@123' },
  { role: 'Teacher', username: 'teacher1', password: 'Teach@123' },
  { role: 'Student', username: 'student1', password: 'Student@123' },
];

function renderLogin(message) {
  const username = el('input', { type: 'text', name: 'username', required: 'required', autocomplete: 'username', placeholder: 'e.g. admin' });
  const password = el('input', { type: 'password', name: 'password', required: 'required', autocomplete: 'current-password', placeholder: 'Your password' });
  const errorBox = el('div');
  if (message) errorBox.appendChild(el('div', { class: 'error-box', text: message }));

  async function doLogin(event) {
    event.preventDefault();
    errorBox.replaceChildren();
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    button.textContent = 'Signing in…';
    try {
      const session = await api('/api/auth/login', {
        method: 'POST', body: { username: username.value.trim(), password: password.value }
      });
      state.user = session;
      await boot();
    } catch (err) {
      errorBox.replaceChildren(el('div', { class: 'error-box', text: err.message }));
      button.disabled = false;
      button.textContent = 'Sign in';
    }
  }

  const form = el('form', { onsubmit: doLogin, autocomplete: 'on' },
    el('div', { class: 'field' }, el('label', { text: 'Username' }), username),
    el('div', { class: 'field' }, el('label', { text: 'Password' }), password),
    el('button', { class: 'btn primary', type: 'submit', text: 'Sign in' })
  );

  const chips = DEMO_LOGINS.map(account =>
    el('button', {
      class: 'demo-chip', type: 'button',
      onclick: () => { username.value = account.username; password.value = account.password; }
    },
      el('strong', { text: account.role }),
      el('span', { text: account.username + ' / ' + account.password })
    )
  );

  clear(appRoot()).appendChild(el('div', { class: 'login-wrap' },
    el('div', { class: 'login-brand' },
      el('div', { class: 'crest', text: 'SMS' }),
      el('h1', { text: 'School Management System' }),
      el('p', { text: 'One central place for student records, classes, attendance, examinations, fees and reports.' }),
      el('ul', {},
        el('li', { text: 'Role-based access for administrators, teachers and students' }),
        el('li', { text: 'Automatic grade computation and class positions' }),
        el('li', { text: 'Attendance, fee tracking and printable result sheets' })
      ),
      el('p', { text: 'Supports SDG 4 — Quality Education.' })
    ),
    el('div', { class: 'login-panel' },
      el('div', { class: 'login-card' },
        el('h2', { text: 'Sign in' }),
        el('p', { class: 'sub', text: 'Enter the credentials issued by your school administrator.' }),
        errorBox, form,
        el('div', { class: 'demo-accounts' }, el('p', { text: 'Demonstration accounts' }), chips)
      )
    )
  ));
}

/* ============================================================= shell */

const NAV_GROUPS = [
  { label: 'Overview', items: [['dashboard', 'Dashboard']] },
  {
    label: 'People',
    items: [['students', 'Students'], ['teachers', 'Teachers'], ['users', 'User accounts']]
  },
  {
    label: 'Academics',
    items: [['classes', 'Classes'], ['subjects', 'Subjects'], ['exams', 'Examinations'], ['attendance', 'Attendance']]
  },
  { label: 'Administration', items: [['fees', 'Fees and payments'], ['reports', 'Reports']] },
  {
    label: 'My information',
    items: [['my-results', 'My results'], ['my-attendance', 'My attendance'], ['my-fees', 'My fees']]
  }
];

const TITLES = {
  dashboard: ['Dashboard', 'School-wide summary for the selected term'],
  students: ['Student management', 'Registration, profiles and enrollment'],
  teachers: ['Teacher management', 'Staff records and subject assignments'],
  classes: ['Class management', 'Classes and subject allocation'],
  subjects: ['Subject management', 'Subjects offered by the school'],
  exams: ['Examination management', 'Exam sessions and marks entry'],
  attendance: ['Attendance management', 'Daily attendance recording and monitoring'],
  fees: ['Fee management', 'Invoices, payments and outstanding balances'],
  reports: ['Report management', 'Academic, attendance and financial reports'],
  users: ['User management', 'Accounts, roles and access permissions'],
  'my-results': ['My results', 'Your report card for the selected term'],
  'my-attendance': ['My attendance', 'Your attendance history'],
  'my-fees': ['My fees', 'Your invoices and payment status']
};

function navigate(route) {
  state.route = route;
  window.location.hash = '#/' + route;
  render();
}

function navItemsForRole(role) {
  const allowed = new Set(state.user.links || []);
  const out = [];
  for (const group of NAV_GROUPS) {
    const items = group.items.filter(([key]) => key === 'dashboard' || allowed.has(key));
    if (items.length) out.push({ label: group.label, items });
  }
  return out;
}

function render() {
  if (!state.user) { renderLogin(); return; }
  const [title, subtitle] = TITLES[state.route] || TITLES.dashboard;
  const role = state.user.role;

  const sidebar = el('aside', { class: 'sidebar', id: 'sidebar' },
    el('div', { class: 'school' },
      el('div', { class: 'mark', text: 'SMS' }),
      el('div', { class: 'name' }, 'Starford School', el('small', { text: 'Management System' }))
    )
  );

  for (const group of navItemsForRole(role)) {
    sidebar.appendChild(el('div', { class: 'nav-group', text: group.label }));
    for (const [key, label] of group.items) {
      sidebar.appendChild(el('button', {
        class: 'nav-item' + (state.route === key ? ' active' : ''),
        text: label, onclick: () => { toggleSidebar(false); navigate(key); }
      }));
    }
  }

  const termSelect = el('select', {
    onchange: event => { ui.term = event.target.value; render(); }
  }, ['First Term', 'Second Term', 'Third Term'].map(t => {
    const o = el('option', { value: t, text: t });
    if (t === ui.term) o.selected = true;
    return o;
  }));

  const topbar = el('header', { class: 'topbar' },
    el('button', {
      class: 'btn sm menu-toggle', text: 'Menu',
      onclick: () => document.getElementById('sidebar').classList.toggle('open')
    }),
    el('div', { class: 'page-title' }, el('h1', { text: title }), el('small', { text: subtitle })),
    el('div', { class: 'field compact' }, el('label', { text: 'Term' }), termSelect),
    el('div', { class: 'userbox' },
      el('div', { class: 'who' }, el('strong', { text: state.user.full_name }), el('span', { text: role })),
      el('div', { class: 'avatar', text: initials(state.user.full_name) }),
      el('button', { class: 'btn sm', text: 'Password', onclick: openPasswordForm }),
      el('button', { class: 'btn sm', text: 'Sign out', onclick: doLogout })
    )
  );

  const main = el('div', { class: 'main' }, topbar, el('main', { class: 'content', id: 'view' }));
  clear(appRoot()).appendChild(el('div', { class: 'shell' }, sidebar, main));

  const view = VIEWS[state.route] || VIEWS.dashboard;
  runView(document.getElementById('view'), view);
}

function toggleSidebar(force) {
  const sidebar = document.getElementById('sidebar');
  if (sidebar) sidebar.classList.toggle('open', force);
}

async function runView(container, view) {
  container.replaceChildren(el('div', { class: 'empty', text: 'Loading…' }));
  try {
    const node = await view(container);
    if (node) container.replaceChildren(node);
  } catch (err) {
    container.replaceChildren(el('div', { class: 'error-box', text: err.message }));
  }
}

async function doLogout() {
  try { await api('/api/auth/logout', { method: 'POST', body: {} }); } catch (err) { /* already signed out */ }
  state.user = null;
  renderLogin();
}

async function openPasswordForm() {
  const result = await openForm({
    title: 'Change my password',
    fields: [
      { name: 'current_password', label: 'Current password', type: 'password', required: true, span: 'full' },
      { name: 'new_password', label: 'New password', type: 'password', required: true, span: 'full', help: 'At least 8 characters.' }
    ],
    onSubmit: payload => api('/api/auth/change-password', { method: 'POST', body: payload })
  });
  if (result) toast('Password changed', 'success');
}

/* ============================================================= shared data */

function classOptions(blankLabel) {
  const rows = [{ value: '', label: blankLabel || 'All classes' }];
  for (const c of (state.ref && state.ref.classes) || []) rows.push({ value: c.id, label: c.name });
  return rows;
}

function subjectOptions() {
  return (state.ref.subjects || []).map(s => ({ value: s.id, label: s.name + ' (' + s.code + ')' }));
}

function teacherOptions() {
  return (state.ref.teachers || []).map(t => ({ value: t.id, label: t.name + ' — ' + t.staff_no }));
}

function qs(params) {
  const parts = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === '' || value === null || value === undefined) continue;
    parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(value));
  }
  return parts.length ? '?' + parts.join('&') : '';
}

/* ============================================================= views */

const VIEWS = {};

VIEWS.dashboard = async () => {
  const data = await api('/api/dashboard' + qs({ term: ui.term, academic_year: ui.year }));

  if (data.role === 'student') {
    const wrap = el('div', {});
    wrap.appendChild(el('div', { class: 'stat-grid' },
      stat('Term average', data.average === null ? '—' : data.average + '%', data.grade ? 'Grade ' + data.grade : '', 'blue'),
      stat('Position', data.position ? data.position + (data.class_size ? ' / ' + data.class_size : '') : '—', 'in class'),
      stat('Attendance', data.attendance ? data.attendance.rate + '%' : '—',
        data.attendance ? data.attendance.attended + ' of ' + data.attendance.total_sessions + ' sessions' : '', 'green'),
      stat('Fees owing', data.fees ? money(data.fees.balance) : '—',
        data.fees && data.fees.balance > 0 ? 'Pay at the bursary' : 'Cleared',
        data.fees && data.fees.balance > 0 ? 'red' : 'green')
    ));
    wrap.appendChild(card('Subjects — ' + data.term, null, subjectBreakdown(data.subjects), true));
    return wrap;
  }

  const wrap = el('div', {});
  wrap.appendChild(el('div', { class: 'stat-grid' },
    stat('Active students', data.counts.students, data.counts.classes + ' class(es)'),
    stat('Teachers', data.counts.teachers, data.counts.subjects + ' subjects offered'),
    stat('Attendance rate', data.attendance_rate + '%', 'Across all recorded sessions', 'green'),
    stat('Fees outstanding', money(data.fees.outstanding),
      money(data.fees.paid) + ' collected of ' + money(data.fees.due), 'amber')
  ));

  const performance = el('div', {});
  if (!data.class_performance.length) performance.appendChild(el('div', { class: 'empty', text: 'No marks recorded yet for this term.' }));
  for (const row of data.class_performance) {
    performance.appendChild(el('div', { class: 'metric-row' },
      el('span', { class: 'name', text: row.name }),
      pctBar(row.average),
      el('span', { class: 'val', text: row.average + '%' })
    ));
  }

  const collectionRate = data.fees.due ? (data.fees.paid / data.fees.due) * 100 : 0;
  wrap.appendChild(el('div', { class: 'form-grid' },
    card('Class performance — ' + data.term, null, performance),
    card('Fee collection — ' + data.term, null, [
      el('div', { class: 'metric-row' },
        el('span', { class: 'name', text: 'Collected' }), pctBar(collectionRate),
        el('span', { class: 'val', text: collectionRate.toFixed(0) + '%' })),
      el('p', { class: 'help', text: 'Billed ' + money(data.fees.due) + ' · Received ' + money(data.fees.paid) + ' · Outstanding ' + money(data.fees.outstanding) })
    ])
  ));

  if (data.my_classes) {
    wrap.appendChild(card('My teaching assignments', null,
      dataTable([
        { label: 'Class', key: 'name' },
        { label: 'Students', key: 'students', className: 'num' }
      ], data.my_classes, 'You have no class assignments.'), true));
  }

  wrap.appendChild(card('Recent system activity', null,
    dataTable([
      { label: 'When', key: 'at' },
      { label: 'User', render: r => r.actor || '—' },
      { label: 'Action', render: r => badge('B', r.action) },
      { label: 'Detail', render: r => el('code', { text: r.detail || '' }) }
    ], data.recent_activity, 'No activity recorded yet.'), true));

  return wrap;
};

function subjectBreakdown(subjects) {
  if (!subjects || !subjects.length) return el('div', { class: 'empty', text: 'No examination records yet.' });
  return dataTable([
    { label: 'Subject', render: r => el('strong', { text: r.subject }) },
    { label: 'Code', render: r => el('code', { text: r.code }) },
    { label: 'Assessments', render: r => r.assessments.map(a => a.score + '/' + a.max_marks).join(', ') },
    { label: 'Average', className: 'num', render: r => r.average + '%' },
    { label: 'Grade', render: r => badge(r.grade, r.grade) },
    { label: 'Remark', render: r => r.remark }
  ], subjects);
}

/* ------------------------------------------------------------ students */

VIEWS.students = async (container) => {
  const params = { ...ui.students, page_size: 12 };
  const data = await api('/api/students' + qs(params));

  const toolbar = el('div', { class: 'toolbar' },
    el('div', { class: 'field compact' },
      el('label', { text: 'Search' }),
      el('input', {
        type: 'search', value: ui.students.q, placeholder: 'Name or admission number',
        onchange: event => { ui.students.q = event.target.value; ui.students.page = 1; render(); }
      })),
    el('div', { class: 'field compact' },
      el('label', { text: 'Class' }),
      el('select', {
        onchange: event => { ui.students.class_id = event.target.value; ui.students.page = 1; render(); }
      }, classOptions().map(o => {
        const node = el('option', { value: o.value, text: o.label });
        if (String(ui.students.class_id) === String(o.value)) node.selected = true;
        return node;
      }))),
    el('div', { class: 'field compact' },
      el('label', { text: 'Sort by' }),
      el('select', {
        onchange: event => { ui.students.sort = event.target.value; render(); }
      }, [['admission_no', 'Admission number'], ['name', 'Surname'], ['class', 'Class']].map(([value, label]) => {
        const node = el('option', { value, text: label });
        if (ui.students.sort === value) node.selected = true;
        return node;
      })))
  );

  const isAdmin = state.user.role === 'admin';
  if (isAdmin) {
    toolbar.appendChild(el('button', {
      class: 'btn primary', text: 'Register student',
      onclick: () => studentForm(null, container)
    }));
  }

  const columns = [
    { label: 'Admission no.', render: r => el('code', { text: r.admission_no }) },
    { label: 'Name', render: r => el('button', { class: 'btn ghost sm', text: r.first_name + ' ' + r.last_name, onclick: () => openStudent(r.id) }) },
    { label: 'Class', render: r => r.class_name || '—' },
    { label: 'Gender', key: 'gender' },
    { label: 'Guardian', render: r => r.guardian_name || '—' },
    { label: 'Status', render: r => badge(r.status) },
    {
      label: 'Actions', className: 'actions', render: r => el('div', { class: 'toolbar' },
        el('button', { class: 'btn sm', text: 'View', onclick: () => openStudent(r.id) }),
        isAdmin && el('button', { class: 'btn sm', text: 'Edit', onclick: () => studentForm(r, container) }),
        isAdmin && el('button', { class: 'btn sm danger', text: 'Delete', onclick: () => deleteStudent(r, container) })
      )
    }
  ];

  return el('div', {},
    card('Students', toolbar, [dataTable(columns, data.rows, 'No students match your filters.'),
      pager(data, page => { ui.students.page = page; render(); })], true));
};

async function openStudent(id) {
  try {
    const data = await api('/api/students/' + id + qs({ term: ui.term, academic_year: ui.year }));
    modal({
      title: data.student.first_name + ' ' + data.student.last_name + ' — ' + data.student.admission_no,
      wide: true,
      body: [reportCard(data.report, true)]
    });
  } catch (err) {
    toast(err.message, 'error');
  }
}

function studentForm(row, container) {
  const fields = [
    { name: 'first_name', label: 'First name', required: true },
    { name: 'last_name', label: 'Last name', required: true },
    { name: 'gender', label: 'Gender', type: 'select', required: true, options: [{ value: 'Male', label: 'Male' }, { value: 'Female', label: 'Female' }] },
    { name: 'class_id', label: 'Class', type: 'select', required: true, options: state.ref.classes.map(c => ({ value: c.id, label: c.name })) },
    { name: 'date_of_birth', label: 'Date of birth', type: 'date' },
    { name: 'enrollment_date', label: 'Enrollment date', type: 'date' },
    { name: 'guardian_name', label: 'Guardian name', span: 'full' },
    { name: 'guardian_phone', label: 'Guardian phone' },
    { name: 'guardian_email', label: 'Guardian email', type: 'email' },
    row ? null : { name: 'admission_no', label: 'Admission number', help: 'Leave blank to generate automatically.' },
    row ? { name: 'status', label: 'Status', type: 'select', required: true, options: ['active', 'graduated', 'withdrawn'].map(v => ({ value: v, label: v })) } : null,
    row ? null : { name: 'create_login', label: 'Create portal login', type: 'select', required: true, options: [{ value: '1', label: 'Yes — assign a login' }, { value: '0', label: 'No' }], default: '1' }
  ].filter(Boolean);

  openForm({
    title: row ? 'Edit student record' : 'Register a new student',
    wide: true, fields, values: row || undefined,
    intro: row ? undefined : 'A portal login will use the password Student@123 by default.',
    onSubmit: async payload => {
      if (payload.guardian_email === undefined && row) payload.guardian_email = row.guardian_email || '';
      if (!row) payload.create_login = payload.create_login === '1';
      const result = row
        ? await api('/api/students/' + row.id, { method: 'PUT', body: payload })
        : await api('/api/students', { method: 'POST', body: payload });
      toast(row ? 'Student record updated' : 'Student registered', 'success');
      if (!row && result.credentials) {
        toast('Portal login: ' + result.credentials.username, 'success');
      }
      render();
      return result;
    }
  });
}

async function deleteStudent(row, container) {
  const ok = await confirmDialog('Delete ' + row.first_name + ' ' + row.last_name + ' (' + row.admission_no +
    ')? Their marks, attendance and fee records will also be removed.');
  if (!ok) return;
  try {
    await api('/api/students/' + row.id, { method: 'DELETE', body: {} });
    toast('Student deleted', 'success');
    render();
  } catch (err) {
    toast(err.message, 'error');
  }
}

/* ------------------------------------------------------------ teachers */

VIEWS.teachers = async () => {
  const data = await api('/api/teachers' + qs({ q: ui.teachers.q, page: ui.teachers.page, page_size: 12 }));
  const isAdmin = state.user.role === 'admin';

  const toolbar = el('div', { class: 'toolbar' },
    el('div', { class: 'field compact' },
      el('label', { text: 'Search' }),
      el('input', {
        type: 'search', value: ui.teachers.q,
        onchange: event => { ui.teachers.q = event.target.value; ui.teachers.page = 1; render(); }
      })),
    isAdmin && el('button', { class: 'btn primary', text: 'Add teacher', onclick: () => teacherForm(null) })
  );

  const columns = [
    { label: 'Staff no.', render: r => el('code', { text: r.staff_no }) },
    { label: 'Name', render: r => r.first_name + ' ' + r.last_name },
    { label: 'Specialization', render: r => r.specialization || '—' },
    { label: 'Qualification', render: r => r.qualification || '—' },
    { label: 'Contact', render: r => r.phone || r.email || '—' },
    { label: 'Subjects', key: 'assignment_count', className: 'num' },
    { label: 'Status', render: r => badge(r.status === 'active' ? 'active' : r.status === 'on leave' ? 'leave' : 'inactive', r.status) },
    {
      label: 'Actions', className: 'actions', render: r => el('div', { class: 'toolbar' },
        el('button', { class: 'btn sm', text: 'Assignments', onclick: () => showTeacher(r.id) }),
        isAdmin && el('button', { class: 'btn sm', text: 'Edit', onclick: () => teacherForm(r) }),
        isAdmin && el('button', { class: 'btn sm danger', text: 'Delete', onclick: async () => {
          if (!await confirmDialog('Delete staff record ' + r.staff_no + '?')) return;
          try { await api('/api/teachers/' + r.id, { method: 'DELETE', body: {} }); toast('Teacher deleted', 'success'); render(); }
          catch (err) { toast(err.message, 'error'); }
        } })
      )
    }
  ];

  return el('div', {}, card('Teaching staff', toolbar,
    [dataTable(columns, data.rows, 'No teachers found.'), pager(data, page => { ui.teachers.page = page; render(); })], true));
};

async function showTeacher(id) {
  const data = await api('/api/teachers/' + id);
  const t = data.teacher;
  modal({
    title: t.first_name + ' ' + t.last_name,
    body: [
      el('div', { class: 'rc-grid' },
        el('div', {}, el('div', { class: 'k', text: 'Staff number' }), el('div', { class: 'v', text: t.staff_no })),
        el('div', {}, el('div', { class: 'k', text: 'Specialization' }), el('div', { class: 'v', text: t.specialization || '—' })),
        el('div', {}, el('div', { class: 'k', text: 'Qualification' }), el('div', { class: 'v', text: t.qualification || '—' })),
        el('div', {}, el('div', { class: 'k', text: 'Hired' }), el('div', { class: 'v', text: t.hire_date || '—' })),
        el('div', {}, el('div', { class: 'k', text: 'Login' }), el('div', { class: 'v', text: t.username || 'none' }))
      ),
      el('h3', { text: 'Teaching assignments' }),
      dataTable([
        { label: 'Class', key: 'class_name' },
        { label: 'Subject', key: 'subject_name' }
      ], data.assignments, 'No subject assignments yet.')
    ]
  });
}

function teacherForm(row) {
  openForm({
    title: row ? 'Edit teacher' : 'Add teacher',
    wide: true,
    fields: [
      { name: 'first_name', label: 'First name', required: true },
      { name: 'last_name', label: 'Last name', required: true },
      { name: 'email', label: 'Email', type: 'email' },
      { name: 'phone', label: 'Phone' },
      { name: 'qualification', label: 'Qualification' },
      { name: 'specialization', label: 'Specialization' },
      { name: 'hire_date', label: 'Hire date', type: 'date' },
      { name: 'staff_no', label: 'Staff number', help: row ? undefined : 'Leave blank to generate automatically.' },
      row ? { name: 'status', label: 'Status', type: 'select', required: true, options: ['active', 'on leave', 'retired'].map(v => ({ value: v, label: v })) } : null
    ].filter(Boolean),
    values: row || undefined,
    onSubmit: async payload => {
      const result = row
        ? await api('/api/teachers/' + row.id, { method: 'PUT', body: payload })
        : await api('/api/teachers', { method: 'POST', body: payload });
      toast(row ? 'Teacher updated' : 'Teacher added' + (result.credentials ? ' — login ' + result.credentials.username : ''), 'success');
      render();
      return result;
    }
  });
}

/* ------------------------------------------------------------ classes */

VIEWS.classes = async () => {
  const data = await api('/api/classes');
  const isAdmin = state.user.role === 'admin';

  const columns = [
    { label: 'Class', render: r => el('strong', { text: r.name }) },
    { label: 'Level', key: 'level' },
    { label: 'Academic year', key: 'academic_year' },
    { label: 'Homeroom teacher', render: r => r.homeroom_name || '—' },
    { label: 'Students', key: 'student_count', className: 'num' },
    {
      label: 'Actions', className: 'actions', render: r => el('div', { class: 'toolbar' },
        el('button', { class: 'btn sm', text: 'Subjects', onclick: () => showClassSubjects(r) }),
        isAdmin && el('button', { class: 'btn sm', text: 'Edit', onclick: () => classForm(r) }),
        isAdmin && el('button', { class: 'btn sm danger', text: 'Delete', onclick: async () => {
          if (!await confirmDialog('Delete class ' + r.name + '?')) return;
          try { await api('/api/classes/' + r.id, { method: 'DELETE', body: {} }); toast('Class deleted', 'success'); render(); }
          catch (err) { toast(err.message, 'error'); }
        } })
      )
    }
  ];

  return el('div', {}, card('Classes',
    isAdmin && [el('button', { class: 'btn primary', text: 'New class', onclick: () => classForm(null) })],
    [dataTable(columns, data.rows, 'No classes defined.'),
      el('p', { class: 'help', text: 'A class cannot be deleted while students are enrolled in it.' })], true));
};

function classForm(row) {
  openForm({
    title: row ? 'Edit class' : 'New class',
    fields: [
      { name: 'name', label: 'Class name', required: true, placeholder: 'e.g. SSS 2A' },
      { name: 'level', label: 'Level', required: true, placeholder: 'e.g. SSS' },
      { name: 'academic_year', label: 'Academic year', required: true, default: '2025/2026' },
      { name: 'homeroom_teacher_id', label: 'Homeroom teacher', type: 'select', options: teacherOptions() }
    ],
    values: row || undefined,
    onSubmit: async payload => {
      if (payload.homeroom_teacher_id === undefined && row) payload.homeroom_teacher_id = row.homeroom_teacher_id;
      if (row) await api('/api/classes/' + row.id, { method: 'PUT', body: payload });
      else await api('/api/classes', { method: 'POST', body: payload });
      toast('Class saved', 'success');
      render();
    }
  });
}

async function showClassSubjects(row) {
  const isAdmin = state.user.role === 'admin';
  const content = el('div', {}, el('div', { class: 'empty', text: 'Loading…' }));
  const select = el('select', { 'aria-label': 'Subject to add' }, subjectOptions());

  async function draw() {
    const data = await api('/api/classes/' + row.id + '/subjects');
    const columns = [
      { label: 'Subject', render: r => el('strong', { text: r.name }) },
      { label: 'Code', render: r => el('code', { text: r.code }) },
      { label: 'Category', render: r => badge('B', r.category) },
      { label: 'Teacher', render: r => r.teacher || 'Unassigned' }
    ];
    if (isAdmin) {
      columns.push({
        label: '', className: 'actions', render: r => el('button', {
          class: 'btn sm danger', text: 'Remove', onclick: async () => {
            try {
              await api('/api/classes/' + row.id + '/subjects/' + r.subject_id, { method: 'DELETE', body: {} });
              toast('Subject removed', 'success');
              draw();
            } catch (err) { toast(err.message, 'error'); }
          }
        })
      });
    }
    content.replaceChildren(dataTable(columns, data.rows, 'No subjects assigned to this class yet.'));
  }

  if (isAdmin) {
    modal({
      title: row.name + ' — subjects',
      body: [
        content,
        el('div', { class: 'toolbar' },
          el('div', { class: 'field compact' }, el('label', { text: 'Add subject' }), select),
          el('button', {
            class: 'btn primary', text: 'Add to class', onclick: async event => {
              const button = event.currentTarget;
              button.disabled = true;
              try {
                await api('/api/classes/' + row.id + '/subjects', { method: 'POST', body: { subject_id: Number(select.value) } });
                toast('Subject added', 'success');
                draw();
              } catch (err) {
                toast(err.message, 'error');
              } finally {
                button.disabled = false;
              }
            }
          })
        )
      ]
    });
  } else {
    modal({ title: row.name + ' — subjects', body: [content] });
  }
  draw();
}

/* ------------------------------------------------------------ subjects */

VIEWS.subjects = async () => {
  const data = await api('/api/subjects');
  const isAdmin = state.user.role === 'admin';
  return el('div', {}, card('Subjects',
    isAdmin && [el('button', { class: 'btn primary', text: 'New subject', onclick: () => subjectForm() })],
    dataTable([
      { label: 'Name', render: r => el('strong', { text: r.name }) },
      { label: 'Code', render: r => el('code', { text: r.code }) },
      { label: 'Category', render: r => badge('B', r.category) },
      isAdmin ? {
        label: 'Actions', className: 'actions', render: r => el('button', {
          class: 'btn sm danger', text: 'Delete', onclick: async () => {
            if (!await confirmDialog('Delete subject ' + r.name + '?')) return;
            try { await api('/api/subjects/' + r.id, { method: 'DELETE', body: {} }); toast('Subject deleted', 'success'); render(); }
            catch (err) { toast(err.message, 'error'); }
          }
        })
      } : null
    ].filter(Boolean), data.rows, 'No subjects defined.'), true));
};

function subjectForm() {
  openForm({
    title: 'New subject',
    fields: [
      { name: 'name', label: 'Subject name', required: true },
      { name: 'code', label: 'Code', required: true, placeholder: 'e.g. MTH' },
      { name: 'category', label: 'Category', type: 'select', required: true, options: [{ value: 'core', label: 'Core' }, { value: 'elective', label: 'Elective' }] }
    ],
    onSubmit: async payload => { await api('/api/subjects', { method: 'POST', body: payload }); toast('Subject added', 'success'); render(); }
  });
}

/* ------------------------------------------------------------ exams & marks */

VIEWS.exams = async () => {
  if (state.examSheet) return marksSheet(state.examSheet);

  const data = await api('/api/exams' + qs({ class_id: '', term: '' }));
  const isAdmin = state.user.role === 'admin';

  return el('div', {}, card('Examination sessions',
    [el('button', { class: 'btn primary', text: 'New exam', onclick: () => examForm() })],
    dataTable([
      { label: 'Exam', render: r => el('strong', { text: r.title }) },
      { label: 'Class', key: 'class_name' },
      { label: 'Subject', key: 'subject_name' },
      { label: 'Term', render: r => r.term + ' · ' + r.academic_year },
      { label: 'Date', key: 'exam_date' },
      { label: 'Max marks', key: 'max_marks', className: 'num' },
      { label: 'Entered', key: 'entries', className: 'num' },
      {
        label: 'Actions', className: 'actions', render: r => el('div', { class: 'toolbar' },
          el('button', { class: 'btn sm primary', text: 'Enter marks', onclick: () => { state.examSheet = r.id; render(); } }),
          isAdmin && el('button', { class: 'btn sm danger', text: 'Delete', onclick: async () => {
            if (!await confirmDialog('Delete this exam session and all its marks?')) return;
            try { await api('/api/exams/' + r.id, { method: 'DELETE', body: {} }); toast('Exam deleted', 'success'); render(); }
            catch (err) { toast(err.message, 'error'); }
          } })
        )
      }
    ], data.rows, 'No examination sessions have been created.'), true));
};

function examForm() {
  openForm({
    title: 'New examination session',
    fields: [
      { name: 'title', label: 'Title', required: true, placeholder: 'e.g. First Term Exam' },
      { name: 'class_id', label: 'Class', type: 'select', required: true, options: state.ref.classes.map(c => ({ value: c.id, label: c.name })) },
      { name: 'subject_id', label: 'Subject', type: 'select', required: true, options: subjectOptions() },
      { name: 'term', label: 'Term', type: 'select', required: true, options: ['First Term', 'Second Term', 'Third Term'].map(v => ({ value: v, label: v })) },
      { name: 'academic_year', label: 'Academic year', required: true, default: '2025/2026' },
      { name: 'exam_date', label: 'Exam date', type: 'date' },
      { name: 'max_marks', label: 'Maximum marks', type: 'number', required: true, default: 100, min: 1, max: 1000 }
    ],
    onSubmit: async payload => { await api('/api/exams', { method: 'POST', body: payload }); toast('Exam session created', 'success'); render(); }
  });
}

async function marksSheet(examId) {
  const data = await api('/api/exams/' + examId + '/marks');
  const exam = data.exam;
  const inputs = {};

  const grid = el('div', { class: 'mark-grid' },
    el('div', { class: 'head', text: 'Student' }),
    el('div', { class: 'head', text: 'Score' }),
    el('div', { class: 'head num', text: 'Percent' }),
    el('div', { class: 'head', text: 'Grade' }),
  );

  const percentCells = {};
  const gradeCells = {};

  for (const row of data.rows) {
    const input = el('input', {
      type: 'number', min: 0, max: exam.max_marks, step: '0.5',
      value: row.score === null ? '' : String(row.score),
      'aria-label': 'Score for ' + row.admission_no
    });
    inputs[row.student_id] = input;
    percentCells[row.student_id] = el('div', { class: 'num', text: '' });
    gradeCells[row.student_id] = el('div', {}, '');

    input.addEventListener('input', () => {
      const raw = input.value === '' ? null : Number(input.value);
      const pct = raw === null || isNaN(raw) ? null : Math.round((raw / exam.max_marks) * 10000) / 100;
      percentCells[row.student_id].textContent = pct === null ? '—' : pct + '%';
      const grade = pct === null ? null : gradeFromScale(pct);
      clear(gradeCells[row.student_id]).appendChild(grade ? badge(grade.grade, grade.grade + ' · ' + grade.remark) : document.createTextNode('—'));
      updateSummary();
    });

    append(grid, [
      el('div', { class: 'who' }, row.first_name + ' ' + row.last_name, el('small', { text: row.admission_no })),
      input, percentCells[row.student_id], gradeCells[row.student_id]
    ]);
    input.dispatchEvent(new Event('input'));
  }

  const summary = el('div', { class: 'mark-summary' });
  function updateSummary() {
    const filled = Object.values(inputs).filter(i => i.value !== '' && !isNaN(Number(i.value)));
    const average = filled.length
      ? Math.round(filled.reduce((sum, i) => sum + Number(i.value), 0) / filled.length * 100) / 100
      : 0;
    clear(summary).append(
      document.createTextNode('Recorded: ' + filled.length + ' of ' + data.rows.length),
      el('span', { text: 'Average score: ' + average }),
      el('span', { text: 'Maximum: ' + exam.max_marks })
    );
  }

  const sheet = el('div', { class: 'card' },
    el('div', { class: 'card-head' },
      el('h2', { class: 'grow' }, exam.subject_name + ' — ' + exam.class_name),
      el('span', { class: 'badge B', text: exam.title + ' · ' + exam.term }),
      el('button', { class: 'btn sm', text: 'Back to exams', onclick: () => { state.examSheet = null; render(); } })
    ),
    el('div', { class: 'card-body' },
      el('p', { class: 'help', text: 'Enter scores out of ' + exam.max_marks +
        '. Blank cells clear any stored mark. Scores outside the range are rejected on save.' }),
      grid, summary,
      el('div', { class: 'toolbar' },
        el('button', {
          class: 'btn primary', text: 'Save all marks', onclick: async event => {
            const button = event.currentTarget;
            button.disabled = true;
            const scores = {};
            for (const [studentId, input] of Object.entries(inputs)) scores[studentId] = input.value === '' ? null : Number(input.value);
            try {
              const result = await api('/api/exams/' + examId + '/marks', { method: 'PUT', body: { scores } });
              toast('Saved ' + result.saved + ' mark(s)' + (result.skipped.length ? ' — ' + result.skipped.length + ' rejected' : ''),
                result.skipped.length ? 'error' : 'success');
              if (result.skipped.length) console.warn('Rejected marks', result.skipped);
              state.examSheet = null;
              render();
            } catch (err) {
              toast(err.message, 'error');
              button.disabled = false;
            }
          }
        })
      )
    )
  );
  updateSummary();
  return sheet;
}

function gradeFromScale(percentage) {
  const scales = state.ref.grade_scales || [];
  return scales.find(s => percentage >= s.min_pct) || null;
}

/* ------------------------------------------------------------ attendance */

VIEWS.attendance = async () => {
  const isAdmin = state.user.role === 'admin';
  const isStudent = state.user.role === 'student';

  if (isStudent) return VIEWS['my-attendance']();

  if (!ui.attendance.class_id) {
    ui.attendance.class_id = String(state.ref.classes[0] ? state.ref.classes[0].id : '');
  }

  const classId = Number(ui.attendance.class_id);
  const roster = await api('/api/students' + qs({ class_id: classId, page_size: 200, status: 'active' }));
  const existing = await api('/api/attendance' + qs({ class_id: classId, date: ui.attendance.date }));
  const recorded = {};
  for (const row of existing.rows) {
    if (row.period === 'Daily') recorded[row.student_id] = row.status;
  }

  const statuses = ['present', 'absent', 'late', 'excused'];
  const chosen = {};
  for (const row of roster.rows) chosen[row.id] = recorded[row.id] || 'present';

  const list = el('div', {});
  for (const row of roster.rows) {
    const group = el('div', { class: 'attend-choices' });
    for (const status of statuses) {
      const button = el('button', {
        class: 'attend-btn' + (chosen[row.id] === status ? ' on ' + status : ''),
        type: 'button', text: status,
        onclick: () => {
          chosen[row.id] = status;
          for (const child of group.children) child.classList.remove('on', ...statuses);
          button.classList.add('on', status);
        }
      });
      group.appendChild(button);
    }
    list.appendChild(el('div', { class: 'mark-grid' },
      el('div', { class: 'who' }, row.first_name + ' ' + row.last_name, el('small', { text: row.admission_no })),
      group, el('div'), el('div')
    ));
  }

  const toolbar = el('div', { class: 'toolbar' },
    el('div', { class: 'field compact' },
      el('label', { text: 'Class' }),
      el('select', {
        onchange: event => { ui.attendance.class_id = event.target.value; render(); }
      }, state.ref.classes.map(c => {
        const node = el('option', { value: c.id, text: c.name });
        if (String(c.id) === ui.attendance.class_id) node.selected = true;
        return node;
      }))),
    el('div', { class: 'field compact' },
      el('label', { text: 'Date' }),
      el('input', {
        type: 'date', value: ui.attendance.date,
        onchange: event => { ui.attendance.date = event.target.value; render(); }
      })),
    el('button', {
      class: 'btn', text: 'Mark all present',
      onclick: () => { for (const id of Object.keys(chosen)) chosen[id] = 'present'; render(); }
    }),
    el('button', {
      class: 'btn primary', text: 'Save attendance', onclick: async event => {
        const button = event.currentTarget;
        button.disabled = true;
        try {
          const records = Object.entries(chosen).map(([student_id, status]) => ({ student_id: Number(student_id), status }));
          const result = await api('/api/attendance', {
            method: 'POST',
            body: { class_id: classId, date: ui.attendance.date, period: 'Daily', records }
          });
          toast('Attendance saved for ' + result.saved + ' student(s)', 'success');
          render();
        } catch (err) {
          toast(err.message, 'error');
          button.disabled = false;
        }
      }
    })
  );

  const alreadyRecorded = Object.keys(recorded).length;
  return el('div', {},
    card('Record daily attendance', toolbar, [
      alreadyRecorded
        ? el('p', { class: 'notice-box', text: alreadyRecorded + ' record(s) already exist for this date — saving will update them.' })
        : el('p', { class: 'help', text: 'No records for this date yet.' }),
      roster.rows.length ? list : el('div', { class: 'empty', text: 'This class has no active students.' })
    ]),
    card('Attendance rates — ' + (ui.attendance.class_id ? '' : 'all classes'), null,
      dataTable([
        { label: 'Student', render: r => r.first_name + ' ' + r.last_name },
        { label: 'Class', key: 'class_name' },
        { label: 'Sessions', key: 'total_sessions', className: 'num' },
        { label: 'Present', key: 'attended', className: 'num' },
        { label: 'Absent', key: 'absent', className: 'num' },
        { label: 'Rate', render: r => el('div', { class: 'metric-row' }, pctBar(r.rate), el('span', { class: 'val', text: r.rate + '%' })) }
      ], (await api('/api/reports/attendance' + qs({ class_id: classId }))).rows,
        'No attendance has been recorded.'), true)
  );
};

/* ------------------------------------------------------------ fees */

VIEWS.fees = async () => {
  if (state.user.role === 'student') return VIEWS['my-fees']();

  const isAdmin = state.user.role === 'admin';
  const data = await api('/api/fees/invoices' + qs({ class_id: ui.fees.class_id, term: ui.fees.term }));

  const totals = data.rows.reduce((acc, r) => {
    acc.due += r.amount_due; acc.paid += r.amount_paid; acc.balance += r.balance; return acc;
  }, { due: 0, paid: 0, balance: 0 });

  const toolbar = el('div', { class: 'toolbar' },
    el('div', { class: 'field compact' },
      el('label', { text: 'Class' }),
      el('select', {
        onchange: event => { ui.fees.class_id = event.target.value; render(); }
      }, classOptions().map(o => {
        const node = el('option', { value: o.value, text: o.label });
        if (ui.fees.class_id === o.value) node.selected = true;
        return node;
      }))),
    el('div', { class: 'field compact' },
      el('label', { text: 'Term' }),
      el('select', {
        onchange: event => { ui.fees.term = event.target.value; render(); }
      }, ['First Term', 'Second Term', 'Third Term'].map(v => {
        const node = el('option', { value: v, text: v });
        if (ui.fees.term === v) node.selected = true;
        return node;
      }))),
    isAdmin && el('button', { class: 'btn primary', text: 'New invoice', onclick: () => invoiceForm() })
  );

  const columns = [
    { label: 'Student', render: r => r.first_name + ' ' + r.last_name },
    { label: 'Admission no.', render: r => el('code', { text: r.admission_no }) },
    { label: 'Class', key: 'class_name' },
    { label: 'Item', key: 'description' },
    { label: 'Term', render: r => r.term },
    { label: 'Due', className: 'num', render: r => money(r.amount_due) },
    { label: 'Paid', className: 'num', render: r => money(r.amount_paid) },
    { label: 'Balance', className: 'num', render: r => r.balance > 0 ? el('strong', { class: 'text-red', text: money(r.balance) }) : badge('paid', 'cleared') },
    isAdmin ? {
      label: 'Actions', className: 'actions', render: r => el('div', { class: 'toolbar' },
        r.balance > 0.005 && el('button', { class: 'btn sm', text: 'Record payment', onclick: () => paymentForm(r) }),
        r.amount_paid === 0 && el('button', {
          class: 'btn sm danger', text: 'Delete', onclick: async () => {
            if (!await confirmDialog('Delete this invoice?')) return;
            try { await api('/api/fees/invoices/' + r.invoice_id, { method: 'DELETE', body: {} }); toast('Invoice deleted', 'success'); render(); }
            catch (err) { toast(err.message, 'error'); }
          }
        })
      )
    } : null
  ].filter(Boolean);

  return el('div', {},
    el('div', { class: 'stat-grid' },
      stat('Billed', money(totals.due), ui.fees.term),
      stat('Collected', money(totals.paid), '', 'green'),
      stat('Outstanding', money(totals.balance), '', totals.balance > 0 ? 'red' : 'green'),
      stat('Collection rate', (totals.due ? (totals.paid / totals.due * 100) : 0).toFixed(0) + '%', '', 'blue')
    ),
    card('Fee invoices and payments', toolbar, dataTable(columns, data.rows, 'No invoices for this selection.'), true));
};

async function invoiceForm() {
  await loadStudentCache();
  openForm({
    title: 'New fee invoice',
    fields: [
      {
        name: 'student_id', label: 'Student', type: 'select', required: true,
        options: state.studentCache.map(s => ({ value: s.id, label: s.admission_no + ' — ' + s.first_name + ' ' + s.last_name }))
      },
      { name: 'description', label: 'Fee item', required: true, placeholder: 'e.g. Tuition fee' },
      { name: 'amount_due', label: 'Amount due', type: 'number', required: true, min: 0, step: '0.01' },
      { name: 'term', label: 'Term', type: 'select', required: true, options: ['First Term', 'Second Term', 'Third Term'].map(v => ({ value: v, label: v })) },
      { name: 'academic_year', label: 'Academic year', required: true, default: '2025/2026' },
      { name: 'issued_on', label: 'Issued on', type: 'date' }
    ],
    onSubmit: async payload => { await api('/api/fees/invoices', { method: 'POST', body: payload }); toast('Invoice created', 'success'); render(); }
  });
  loadStudentCache();
}

async function loadStudentCache() {
  if (state.studentCache) return;
  const data = await api('/api/students' + qs({ page_size: 200, status: 'active' }));
  state.studentCache = data.rows;
}

function paymentForm(invoice) {
  openForm({
    title: 'Record payment — ' + invoice.description,
    intro: 'Outstanding balance: ' + money(invoice.balance),
    fields: [
      { name: 'amount', label: 'Amount received', type: 'number', required: true, min: 0.01, max: invoice.balance, step: '0.01', default: invoice.balance },
      {
        name: 'method', label: 'Payment method', type: 'select', required: true,
        options: ['cash', 'bank transfer', 'mobile money', 'cheque'].map(v => ({ value: v, label: v }))
      },
      { name: 'reference', label: 'Receipt / reference number' },
      { name: 'paid_on', label: 'Date paid', type: 'date' }
    ],
    onSubmit: async payload => {
      await api('/api/fees/payments', { method: 'POST', body: { ...payload, invoice_id: invoice.invoice_id } });
      toast('Payment recorded', 'success');
      render();
    }
  });
}

/* ------------------------------------------------------------ reports */

VIEWS.reports = async () => {
  if (!ui.reports.class_id && state.ref.classes.length) ui.reports.class_id = String(state.ref.classes[0].id);

  const tabs = el('div', { class: 'tabs' }, [['results', 'Academic results'], ['attendance', 'Attendance'], ['fees', 'Fees']].map(([key, label]) =>
    el('button', {
      class: 'tab' + (ui.reports.tab === key ? ' active' : ''), text: label,
      onclick: () => { ui.reports.tab = key; render(); }
    })));

  const filters = el('div', { class: 'toolbar' },
    el('div', { class: 'field compact' },
      el('label', { text: 'Class' }),
      el('select', {
        onchange: event => { ui.reports.class_id = event.target.value; render(); }
      }, state.ref.classes.map(c => {
        const node = el('option', { value: c.id, text: c.name });
        if (ui.reports.class_id === String(c.id)) node.selected = true;
        return node;
      }))))

  const exportLink = el('a', {
    class: 'btn', text: 'Download CSV',
    href: '/api/reports/export/' + ui.reports.tab + qs({ class_id: ui.reports.class_id, term: ui.term, academic_year: ui.year })
  });

  const body = el('div', {}, el('div', { class: 'empty', text: 'Loading…' }));
  const panel = el('div', {}, tabs, card('Report', [filters, exportLink], body));

  const classId = Number(ui.reports.class_id);
  try {
    if (ui.reports.tab === 'results') {
      const data = await api('/api/reports/results' + qs({ class_id: classId, term: ui.term, academic_year: ui.year }));
      body.replaceChildren(
        el('p', { class: 'help', text: data.class.name + ' · ' + data.term + ' · ' + data.academic_year }),
        dataTable([
          { label: 'Position', className: 'num', render: r => r.position || '—' },
          { label: 'Admission no.', render: r => el('code', { text: r.admission_no }) },
          { label: 'Student', key: 'name' },
          { label: 'Subjects', key: 'subjects_assessed', className: 'num' },
          { label: 'Average', className: 'num', render: r => r.average === null ? '—' : r.average + '%' },
          { label: 'Grade', render: r => r.grade ? badge(r.grade, r.grade) : '—' }
        ], data.results, 'No marks recorded for this class and term.'),
        el('button', { class: 'btn', text: 'Print this sheet', onclick: () => window.print() })
      );
    } else if (ui.reports.tab === 'attendance') {
      const data = await api('/api/reports/attendance' + qs({ class_id: classId }));
      body.replaceChildren(dataTable([
        { label: 'Admission no.', render: r => el('code', { text: r.admission_no }) },
        { label: 'Student', render: r => r.first_name + ' ' + r.last_name },
        { label: 'Class', key: 'class_name' },
        { label: 'Sessions', key: 'total_sessions', className: 'num' },
        { label: 'Present', key: 'attended', className: 'num' },
        { label: 'Absent', key: 'absent', className: 'num' },
        { label: 'Rate', render: r => el('div', { class: 'metric-row' }, pctBar(r.rate), el('span', { class: 'val', text: r.rate + '%' })) }
      ], data.rows, 'No attendance recorded.'));
    } else {
      const data = await api('/api/reports/fees' + qs({ class_id: classId, term: ui.term, academic_year: ui.year }));
      body.replaceChildren(
        el('div', { class: 'stat-grid' },
          stat('Billed', money(data.totals.due)),
          stat('Collected', money(data.totals.paid), '', 'green'),
          stat('Outstanding', money(data.totals.balance), '', 'red')),
        dataTable([
          { label: 'Admission no.', render: r => el('code', { text: r.admission_no }) },
          { label: 'Student', render: r => r.first_name + ' ' + r.last_name },
          { label: 'Class', key: 'class_name' },
          { label: 'Due', className: 'num', render: r => money(r.amount_due) },
          { label: 'Paid', className: 'num', render: r => money(r.amount_paid) },
          { label: 'Balance', className: 'num', render: r => money(r.balance) }
        ], data.rows, 'No fee records.')
      );
    }
  } catch (err) {
    body.replaceChildren(el('div', { class: 'error-box', text: err.message }));
  }

  return el('div', {}, panel);
};

/* ------------------------------------------------------------ users */

VIEWS.users = async () => {
  const data = await api('/api/users');
  return el('div', {},
    card('System accounts',
      [el('button', { class: 'btn primary', text: 'New account', onclick: () => userForm() })],
      [dataTable([
        { label: 'Username', render: r => el('code', { text: r.username }) },
        { label: 'Full name', key: 'full_name' },
        { label: 'Email', render: r => r.email || '—' },
        { label: 'Role', render: r => badge(r.role === 'admin' ? 'B' : r.role === 'teacher' ? 'C' : 'active', r.role) },
        { label: 'Status', render: r => badge(r.is_active ? 'active' : 'withdrawn', r.is_active ? 'active' : 'disabled') },
        {
          label: 'Actions', className: 'actions', render: r => el('div', { class: 'toolbar' },
            el('button', { class: 'btn sm', text: 'Reset password', onclick: () => resetPasswordForm(r) }),
            el('button', {
              class: 'btn sm', text: r.is_active ? 'Disable' : 'Enable', onclick: async () => {
                try {
                  await api('/api/users/' + r.id + '/active', { method: 'PUT', body: { is_active: !r.is_active } });
                  toast('Account updated', 'success'); render();
                } catch (err) { toast(err.message, 'error'); }
              }
            }),
            el('button', {
              class: 'btn sm danger', text: 'Delete', onclick: async () => {
                if (!await confirmDialog('Delete account ' + r.username + '?')) return;
                try { await api('/api/users/' + r.id, { method: 'DELETE', body: {} }); toast('Account deleted', 'success'); render(); }
                catch (err) { toast(err.message, 'error'); }
              }
            })
          )
        }
      ], data.rows),
        el('p', { class: 'help', text: 'Disabling an account immediately revokes its active sessions. Accounts linked to a student or staff record must be removed through that module.' })
      ], true));
};

function userForm() {
  openForm({
    title: 'New system account',
    fields: [
      { name: 'full_name', label: 'Full name', required: true },
      { name: 'username', label: 'Username', required: true },
      { name: 'email', label: 'Email', type: 'email' },
      { name: 'role', label: 'Role', type: 'select', required: true, options: [{ value: 'admin', label: 'Administrator' }, { value: 'teacher', label: 'Teacher' }, { value: 'student', label: 'Student' }] },
      { name: 'password', label: 'Password', required: true, help: 'Minimum 8 characters.' }
    ],
    onSubmit: async payload => { await api('/api/users', { method: 'POST', body: payload }); toast('Account created', 'success'); render(); }
  });
}

function resetPasswordForm(user) {
  openForm({
    title: 'Reset password — ' + user.username,
    fields: [{ name: 'password', label: 'New password', type: 'password', required: true, help: 'Minimum 8 characters.' }],
    onSubmit: async payload => { await api('/api/users/' + user.id + '/password', { method: 'PUT', body: payload }); toast('Password reset', 'success'); }
  });
}

/* ------------------------------------------------------------ student self-service */

VIEWS['my-results'] = async () => {
  const me = await api('/api/auth/me');
  if (!me.record_id) return el('div', { class: 'error-box', text: 'No student record is linked to your account.' });
  const data = await api('/api/students/' + me.record_id + qs({ term: ui.term, academic_year: ui.year }));
  return el('div', { class: 'content-narrow' },
    el('div', { class: 'toolbar' },
      el('button', { class: 'btn primary', text: 'Print report card', onclick: () => window.print() })),
    reportCard(data.report, false));
};

VIEWS['my-attendance'] = async () => {
  const data = await api('/api/attendance');
  const s = data.summary;
  return el('div', { class: 'content-narrow' },
    s && el('div', { class: 'stat-grid' },
      stat('Sessions recorded', s.total_sessions),
      stat('Attended', s.attended, '', 'green'),
      stat('Absent', s.absent, '', s.absent > 0 ? 'red' : 'green'),
      stat('Attendance rate', s.rate + '%', '', s.rate >= 80 ? 'green' : 'amber')),
    card('Attendance history', null, dataTable([
      { label: 'Date', key: 'date' },
      { label: 'Period', key: 'period' },
      { label: 'Status', render: r => badge(r.status) },
      { label: 'Note', render: r => r.note || '—' }
    ], data.rows, 'No attendance has been recorded for you yet.'), true));
};

VIEWS['my-fees'] = async () => {
  const data = await api('/api/fees/invoices' + qs({ term: ui.term }));
  const totals = data.rows.reduce((a, r) => ({ due: a.due + r.amount_due, paid: a.paid + r.amount_paid, balance: a.balance + r.balance }), { due: 0, paid: 0, balance: 0 });
  return el('div', { class: 'content-narrow' },
    el('div', { class: 'stat-grid' },
      stat('Billed', money(totals.due), ui.term),
      stat('Paid', money(totals.paid), '', 'green'),
      stat('Outstanding', money(totals.balance), '', totals.balance > 0 ? 'red' : 'green')),
    card('My invoices', null, dataTable([
      { label: 'Item', key: 'description' },
      { label: 'Term', key: 'term' },
      { label: 'Year', key: 'academic_year' },
      { label: 'Due', className: 'num', render: r => money(r.amount_due) },
      { label: 'Paid', className: 'num', render: r => money(r.amount_paid) },
      { label: 'Balance', className: 'num', render: r => r.balance > 0 ? money(r.balance) : badge('paid', 'cleared') }
    ], data.rows, 'No invoices issued to you.'), true));
};

/* ============================================================= report card */

function reportCard(report, showTitle) {
  const s = report.student;
  const att = report.attendance;
  const fees = report.fees;

  return el('div', { class: 'report-card' },
    el('div', { class: 'rc-head' },
      el('div', {},
        el('div', { class: 'school-name', text: 'Starford International School' }),
        el('div', { class: 'school-sub', text: 'Academic Report Sheet' })
      ),
      el('div', { class: 'doc-title' },
        el('div', { text: report.term }),
        el('div', { text: 'Session: ' + report.academic_year })
      )
    ),
    el('div', { class: 'rc-grid' },
      rcItem('Student', s.first_name + ' ' + s.last_name),
      rcItem('Admission number', s.admission_no),
      rcItem('Class', s.class_name || '—'),
      rcItem('Gender', s.gender),
      rcItem('Guardian', s.guardian_name || '—')
    ),
    dataTable([
      { label: 'Subject', render: r => el('strong', { text: r.subject }) },
      { label: 'Assessments (score / max)', render: r => r.assessments.map(a => a.score + '/' + a.max_marks).join(' · ') },
      { label: 'Average', className: 'num', render: r => r.average + '%' },
      { label: 'Grade', render: r => badge(r.grade, r.grade) },
      { label: 'Remark', render: r => r.remark }
    ], report.subjects, 'No examination records for this term.'),
    el('div', { class: 'rc-summary' },
      rcTile('Overall average', report.overall_average === null ? '—' : report.overall_average + '%'),
      rcTile('Grade', report.overall_grade || '—'),
      rcTile('Position', report.position ? report.position + (report.class_size ? ' of ' + report.class_size : '') : '—'),
      rcTile('Attendance', att ? att.rate + '%' : '—'),
      rcTile('Fees owing', fees ? money(fees.balance) : '—')
    ),
    el('p', { class: 'help', text: 'Grading scale: ' + (state.ref.grade_scales || [])
      .slice().sort((a, b) => b.min_pct - a.min_pct)
      .map(g => g.grade + ' (' + Math.round(g.min_pct) + '–' + Math.round(g.max_pct) + '%)').join(', ') }),
    showTitle ? null : el('p', { class: 'help', text: 'Generated by the School Management System on ' + new Date().toLocaleDateString('en-NG') + '.' })
  );
}

function rcItem(label, value) {
  return el('div', {}, el('div', { class: 'k', text: label }), el('div', { class: 'v', text: String(value) }));
}

function rcTile(label, value) {
  return el('div', { class: 'rc-tile' }, el('div', { class: 'k', text: label }), el('div', { class: 'v', text: String(value) }));
}

/* ============================================================= boot */

async function boot() {
  state.ref = await api('/api/reference');
  if (state.ref.years && state.ref.years.length) ui.year = state.ref.years[0];
  render();
}

async function init() {
  const hash = window.location.hash.replace(/^#\//, '');
  if (hash) state.route = hash;
  try {
    const user = await api('/api/auth/me');
    state.user = { ...user, links: user.links };
    await boot();
  } catch (err) {
    renderLogin();
  }

  window.addEventListener('hashchange', () => {
    const route = window.location.hash.replace(/^#\//, '') || 'dashboard';
    if (route !== state.route) {
      if (route === 'exams') state.examSheet = null;
      state.route = route;
      render();
    }
  });
}

document.addEventListener('DOMContentLoaded', init);
