(() => {
  'use strict';
  const form = document.getElementById('member-form');
  const username = document.getElementById('username');
  const password = document.getElementById('password');
  const status = document.getElementById('status');
  const submit = form.querySelector('button');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submit.disabled) return;
    submit.disabled = true;
    status.textContent = 'Se verifică…';
    try {
      const response = await fetch('/auth/member-login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.value, password: password.value }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Conectarea nu a reușit.');
      password.value = '';
      location.replace('/');
    } catch (error) {
      status.textContent = error.message;
      submit.disabled = false;
    }
  });
})();
