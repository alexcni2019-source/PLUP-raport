"""Public colleague sign-in form."""


def page():
    return """<!doctype html>
<html lang="ro"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conectare colegi · PLUP</title>
<link rel="stylesheet" href="/auth/style.css">
<script src="/auth/member.js" defer></script></head>
<body><main>
<div class="brand">NRG CABLES · PLUP</div>
<h1>Conectare colegi</h1>
<p>Introdu utilizatorul și parola primite de la administratorul PLUP.</p>
<form id="member-form" method="post" action="/auth/member-login">
  <label for="username">Utilizator</label>
  <input id="username" autocomplete="username" autocapitalize="none" spellcheck="false" maxlength="254" required>
  <label for="password">Parolă</label>
  <input id="password" type="password" autocomplete="current-password" minlength="12" maxlength="128" required>
  <button type="submit">Intră în PLUP</button>
</form>
<p id="status" role="status" aria-live="polite"></p>
<p class="help">Ai uitat parola? Cere administratorului PLUP să îți seteze una nouă.</p>
<a class="secondary" href="/">Înapoi la conectare</a>
</main></body></html>
""".encode()
