# CrimTrack — Frontend

Interface web pour l'API CrimTrack. **Aucune installation requise** (pas de
Node.js, pas de npm) : c'est du HTML/CSS/JS pur, React est chargé depuis un
CDN directement dans le navigateur.

## Lancer le frontend

1. Assure-toi que le **backend tourne déjà** (dans son propre terminal) :
   ```
   cd crimtrack-backend
   set DATABASE_URL=sqlite:///./crimtrack.db
   set JWT_SECRET_KEY=dev-secret-key
   uvicorn app.main:app --reload
   ```

2. Dans un **second terminal**, va dans ce dossier (`crimtrack-frontend`) et lance :
   ```
   python -m http.server 5173
   ```

3. Ouvre ton navigateur sur : **http://localhost:5173**

Le port **5173** n'est pas un hasard : c'est celui que le backend autorise
par défaut (CORS). Si tu sers le frontend sur un autre port, ajoute-le à la
variable d'environnement `CORS_ORIGINS` du backend avant de le relancer.

## Se connecter

Il faut un compte utilisateur pour se connecter. Le backend fournit un
script qui crée un jeu de données de démo, avec un compte par rôle :

```
cd crimtrack-backend
python -m app.seed
```

Comptes créés (mot de passe par défaut `ChangeMe123!`, à changer avant tout
usage réel) :
- `admin@crimtrack.local` — administrateur
- `opj@crimtrack.local` — OPJ
- `enqueteur@crimtrack.local` — enquêteur
- `analyste@crimtrack.local` — analyste

## Si l'API tourne ailleurs

Modifie `config.js` (une seule ligne) :
```js
window.CRIMTRACK_API_BASE = "http://127.0.0.1:8000";
```

## Ce que couvre cette interface

Connexion (JWT + rafraîchissement automatique), tableau de bord et points
chauds, incidents (liste/création/export CSV-PDF), personnes, véhicules,
preuves avec chaîne de custody (hash-chain, export CSV/PDF) et pièces
jointes (upload/téléchargement/suppression), relations et recherche de
chemin entre individus, lectures ANPR, journal d'audit (OPJ/admin), purge
RGPD et gestion des comptes (admin).

Les droits d'écriture suivent le RBAC du backend : les boutons de création
n'apparaissent que si ton rôle y est autorisé (l'API les bloquerait de toute
façon côté serveur si tu forçais la main).
