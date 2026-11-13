# Conturi pentru colegi

Proprietarul intră cu GitHub și deschide **Echipă → Creează cont de coleg**.
Completează utilizatorul, parola, rolul și modulele permise. Contul este activ
imediat. Colegul se conectează la `/auth/member-login` cu datele primite.

Cititorii consultă și exportă rapoarte. Editorii pot și lucra în modulele
permise. Doar proprietarul administrează conturile. Schimbarea parolei sau
revocarea accesului închide sesiunile existente. Proprietarul poate reactiva
un cont revocat prin setarea unei parole noi.

Parolele se păstrează ca hashuri scrypt cu salt. Conturile vechi active
acceptă identificatorul existent. Conturile în așteptare se pot activa prin
setarea unei parole în Echipă. Linkurile vechi duc la pagina de conectare.
