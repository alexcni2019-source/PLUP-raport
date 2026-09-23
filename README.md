# NRG Cables · PLUP

Aplicație pentru planul de producție și rapoartele PLUP de o zi sau de weekend. Interfața este adaptată pentru PC, Android și iOS; backendul este Python, cu SQLite pentru istoric și Pillow pentru generarea imaginilor PNG. Valorile rămân în baza de date a serverului după salvare, iar imaginile sunt generate la cerere. Fluxul trebuie verificat în browsere mobile reale înainte de distribuirea URL-ului privat.

## Rulare locală

```bash
python -m pip install -r requirements.txt
python -m server.app
```

Deschide `http://127.0.0.1:8000`. Serverul local ascultă doar pe loopback și nu cere parolă. Pentru un test separat, setează `PLUP_DB_PATH` către o bază de date temporară.

## Găzduire privată

Imaginea Docker servește frontendul și API-ul de pe **același domeniu**. Configurează un proxy HTTPS și un volum persistent montat la `/data`. Setează secretele `PLUP_PASSWORD` (minimum 16 caractere) și `PLUP_SESSION_SECRET` (minimum 32 caractere); aplicația refuză să pornească pe o interfață de rețea fără ele. Nu expune portul 8000 direct pe internet. Protejează accesul și în platforma de găzduire, pe lângă parola aplicației. Fă backup periodic la volumul SQLite.

Pentru Railway: conectează ramura `codex/private-plup-dashboard` ca sursă Docker, montează un volum la `/data`, setează cele două secrete în Variables și adaugă `RAILWAY_RUN_UID=0`. Scriptul de pornire setează drepturile volumului, apoi rulează serverul cu utilizatorul 10001. Configurează healthcheck `/health` și backup zilnic pentru volum. Nu genera domeniul public până când accesul extern protejat prin autentificare a fost aprobat; un serviciu cu domeniu Railway este accesibil pe internet până la ecranul de autentificare.

```bash
docker build -t plup-report .
docker run --rm -p 127.0.0.1:8000:8000 -v plup-data:/data \
  -e PLUP_PASSWORD='o-parola-lunga-unica' \
  -e PLUP_SESSION_SECRET='un-secret-aleator-de-minimum-32-caractere' \
  plup-report
```

Valorile din exemplul de mai sus sunt demonstrative; folosește secrete generate în platforma de găzduire. Nu comite rapoarte sau baza de date în GitHub. Un push pe ramura `main` a repository-ului public poate actualiza pagina publică existentă, astfel că noua aplicație trebuie integrată doar după configurarea găzduirii private.

## Rapoarte

- Plan: rânduri separate AL/CU, câmpurile din model, totaluri calculate și imagine tabelară PNG.
- Zilnic: luni–joi, valori în tone, procent deșeu și indicatori operaționali.
- Weekend: vineri–duminică separat, trei imagini zilnice și imaginea totalului.
- Istoric: fiecare salvare creează o intrare nouă, cu dată și ora salvării; o intrare poate fi redeschisă.

Imaginile sunt generate pe server din date validate. Pe iOS, imaginea se poate salva prin apăsare lungă din previzualizare, dacă navigatorul nu descarcă direct fișierul.
