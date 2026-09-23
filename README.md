# NRG Cables · PLUP

Aplicație pentru planul de producție și rapoartele PLUP de o zi sau de weekend. Interfața este adaptată pentru PC, Android și iOS; backendul este Python, cu SQLite pentru istoric și Pillow pentru generarea imaginilor PNG. Valorile rămân în baza de date a serverului după salvare, iar imaginile sunt generate la cerere. Fluxul trebuie verificat în browsere mobile reale înainte de distribuirea URL-ului privat.

## Rulare locală

```bash
python -m pip install -r requirements.txt
python -m server.app
```

Deschide `http://127.0.0.1:8000`. Serverul local ascultă doar pe loopback și nu cere parolă. Pentru un test separat, setează `PLUP_DB_PATH` către o bază de date temporară.

## Găzduire privată

Imaginea Docker servește frontendul și API-ul de pe **același domeniu**. Configurează un volum persistent montat la `/data`. Setează secretele `PLUP_PASSWORD` (minimum 16 caractere) și `PLUP_SESSION_SECRET` (minimum 32 caractere); aplicația refuză să pornească pe o interfață de rețea fără ele. Nu expune portul 8000 direct pe internet. Fă backup periodic la volumul SQLite.

### Varianta aleasă: acces numai prin Tailscale

Folosește `Dockerfile.private` pentru serviciul Railway. Această imagine rulează aplicația Python și Tailscale Serve în același container. Configurează variabilele secrete `TS_AUTHKEY` (cheie de **unică folosință**, neefemeră, creată în contul Tailscale), `PLUP_PASSWORD` și `PLUP_SESSION_SECRET`, plus `RAILWAY_RUN_UID=0` pentru drepturile volumului. Montează un volum persistent la `/data`: acesta păstrează atât istoricul SQLite, cât și identitatea nodului Tailscale. La repornire, nodul existent folosește starea persistentă și nu reutilizează cheia consumată. **Nu crea un domeniu Railway și nu activa Tailscale Funnel.** `tailscale serve` oferă HTTPS doar dispozitivelor autorizate în tailnet. Activează HTTPS pentru tailnet și limitează prin regulile Tailscale cine poate accesa nodul `plup-raport`; păstrează și parola aplicației. PC-ul și telefoanele Android/iOS trebuie să aibă clientul Tailscale instalat și conectat. Verifică URL-ul `https://plup-raport.<tailnet>.ts.net` afișat în Tailscale după instalare; numele exact depinde de cont.

În Railway setează calea Dockerfile la `Dockerfile.private`, branchul sursă la `codex/private-plup-dashboard`, volumul la `/data` și healthcheck la `/health`. Nu configura Public Networking. Creează o copie de siguranță a volumului și testează restaurarea înainte de folosirea cu date de producție. Cheia de autentificare Tailscale se introduce doar în secret managerul gazdei, niciodată în GitHub sau în conversație. Nodul poate cere reautentificare când expiră cheia dispozitivului.

Varianta aceasta necesită un cont Tailscale administrat de proprietar; configurația este pregătită, însă URL-ul și fluxul Android/iOS trebuie validate după conectarea reală a contului și a serviciului.

### Variantă alternativă cu proxy HTTPS

`Dockerfile` servește aplicația în spatele unui proxy HTTPS extern. Folosește-l doar dacă proxy-ul impune verificarea identității și originea nu poate fi accesată direct. Accesul printr-un domeniu Railway simplu ar expune pagina de autentificare pe internet.

Pentru varianta alternativă pe Railway: conectează ramura `codex/private-plup-dashboard` ca sursă Docker, montează un volum la `/data`, setează cele două secrete în Variables și adaugă `RAILWAY_RUN_UID=0`. Scriptul de pornire setează drepturile volumului, apoi rulează serverul cu utilizatorul 10001. Configurează healthcheck `/health` și backup zilnic pentru volum.

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
- Import plan din imagine: JPG, PNG sau WebP cu tabelul PLUP fotografiat frontal ori capturat; Tesseract propune un draft, marchează cifrele nesigure și cere confirmare înainte de salvare. Imaginea este procesată doar în memorie, fără stocare; tabelul trebuie verificat integral deoarece OCR poate citi greșit zecimalele.
- Import din clipboard: butonul „Lipește imaginea” citește imaginea copiată după gestul utilizatorului; Ctrl/⌘+V funcționează în plan pe desktop. Pe iOS, dacă browserul nu permite citirea directă, apasă lung în caseta de lipire și alege „Lipește”. Textul lipit nu se trimite la server.
- Zilnic: luni–joi, valori în tone, procent deșeu și indicatori operaționali.
- Weekend: vineri–duminică separat, trei imagini zilnice și imaginea totalului.
- Istoric: fiecare salvare creează o intrare nouă, cu dată și ora salvării; o intrare poate fi redeschisă.

Imaginile sunt generate pe server din date validate. Pe iOS, imaginea se poate salva prin apăsare lungă din previzualizare, dacă navigatorul nu descarcă direct fișierul.
