# CrimTrack — Backend (API)

API FastAPI exposant le socle de données commun décrit dans le cahier des
charges (section 4.1) : cartographie/hotspots (Module 1), dossiers &
chaîne de custody (Module 2), réseaux criminels (Module 3), ANPR (Module 4),
authentification RBAC et journal d'audit (sections 2.2 / 4.3).

## Installation rapide (SQLite, sans Docker)

```bash
cd crimtrack-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python -m app.seed          # peuple la base + crée les comptes de démo
uvicorn app.main:app --reload
```

L'API est servie sur http://localhost:8000, la doc interactive sur
http://localhost:8000/docs.

Le frontend (`crimtrack-frontend`, `.env` → `VITE_API_BASE_URL=http://localhost:8000`)
s'y connecte directement ; le bandeau "Mode démonstration" disparaît dès
que l'API répond.

## Avec Docker (PostgreSQL + PostGIS, stack recommandée)

```bash
docker compose up --build
```

Lance l'API sur le port 8000 et une base PostgreSQL/PostGIS sur le port
5432. Pensez à lancer le seed une fois les conteneurs démarrés :

```bash
docker compose exec api python -m app.seed
```

## Authentification (RBAC)

Toutes les routes métier (`/incidents`, `/personnes`, `/vehicules`,
`/relations`, `/preuves`, `/anpr`) exigent désormais un token JWT. Quatre
rôles sont définis (cahier des charges 4.3) : `enqueteur`, `analyste`,
`opj`, `administrateur`.

- Lecture (`GET`) : accessible à tout utilisateur authentifié, quel que
  soit son rôle.
- Écriture (`POST`) sur incidents/personnes/vehicules/relations/preuves/
  custody/ANPR : réservée à `enqueteur`, `opj`, `administrateur` (`analyste`
  est en lecture seule — c'est son cœur de métier : hotspots, graphe de
  relations).
- Gestion des comptes (`POST/GET /auth`) et consultation du journal
  d'audit (`GET /audit`) : réservées à `administrateur` (et `opj` pour
  l'audit).

`python -m app.seed` crée un compte par rôle (mot de passe par défaut
`ChangeMe123!`, à changer via `SEED_ADMIN_PASSWORD` dans `.env` — **ne pas
utiliser tel quel en production**) :

| Email | Rôle |
|---|---|
| admin@crimtrack.local | administrateur |
| opj@crimtrack.local | opj |
| enqueteur@crimtrack.local | enqueteur |
| analyste@crimtrack.local | analyste |

Connexion :

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@crimtrack.local&password=ChangeMe123!"
# → {"access_token": "...", "token_type": "bearer", "role": "administrateur", ...}
```

Puis, sur chaque appel API :

```bash
curl http://localhost:8000/incidents -H "Authorization: Bearer <access_token>"
```

⚠️ `JWT_SECRET_KEY` a une valeur de développement par défaut dans
`app/auth.py` — **à surcharger obligatoirement** via la variable
d'environnement (voir `.env.example`) avant tout déploiement.

## Endpoints disponibles

| Méthode | Route | Rôle requis | Description |
|---|---|---|---|
| POST | `/auth/login` | — (public) | Connexion, renvoie un token JWT |
| GET | `/auth/me` | authentifié | Profil de l'utilisateur courant |
| POST | `/auth` | administrateur | Créer un compte utilisateur |
| GET | `/auth` | administrateur | Lister les comptes |
| GET | `/incidents` | authentifié | Liste des incidents, filtres `statut`, `type_infraction`, `limit` |
| GET | `/incidents/analyse/hotspots` | authentifié | Détection de zones à forte concentration (clustering par grille) |
| GET | `/incidents/{id}` | authentifié | Détail d'un incident |
| POST | `/incidents` | enqueteur/opj/administrateur | Créer un incident |
| GET | `/personnes` | authentifié | Liste des personnes |
| GET | `/personnes/{id}` | authentifié | Détail (consultation journalisée — donnée nominative sensible) |
| POST | `/personnes` | enqueteur/opj/administrateur | Créer une personne |
| GET | `/vehicules` | authentifié | Liste des véhicules |
| POST | `/vehicules` | enqueteur/opj/administrateur | Créer un véhicule |
| GET | `/relations` | authentifié | Liste brute des relations personne↔personne |
| POST | `/relations` | enqueteur/opj/administrateur | Créer une relation |
| **GET** | **`/relations/graphe`** | authentifié | **Graphe construit automatiquement (nœuds + liens), filtrable par `type_relation` et `poids_min`** |
| GET | `/preuves` | authentifié | Liste des preuves, filtre `incident_id` |
| POST | `/preuves` | enqueteur/opj/administrateur | Créer une fiche de preuve |
| GET | `/preuves/{id}/custody` | authentifié | Chaîne de custody + vérification d'intégrité (`chaine_intacte`, `alerte_rupture`) |
| POST | `/preuves/{id}/custody` | enqueteur/opj/administrateur | Ajouter un maillon (collecte/transfert/analyse/restitution) |
| GET | `/preuves/{id}/custody/export.csv` | authentifié | Export CSV de l'historique de custody |
| GET | `/preuves/{id}/custody/export.pdf` | authentifié | Export PDF de l'historique de custody (pièce de procédure) |
| GET | `/preuves/{id}/pieces-jointes` | authentifié | Liste des fichiers rattachés à une preuve |
| POST | `/preuves/{id}/pieces-jointes` | enqueteur/opj/administrateur | Upload d'un fichier (multipart, champ `fichier`) |
| GET | `/preuves/{id}/pieces-jointes/{piece_id}/telechargement` | authentifié | Téléchargement (vérifie le hash SHA-256 avant de servir le fichier) |
| DELETE | `/preuves/{id}/pieces-jointes/{piece_id}` | opj/administrateur | Suppression d'une pièce jointe |
| GET | `/anpr/lectures` | authentifié | Historique des lectures ANPR, filtres `plaque`, `vehicule_id` |
| POST | `/anpr/lectures` | enqueteur/opj/administrateur | Enregistrer une lecture ; rapprochement auto + alerte si véhicule signalé/volé |
| GET | `/audit` | opj/administrateur | Consultation du journal d'audit |
| **GET** | **`/relations/chemin`** | authentifié | **Recherche du chemin le plus court (`depart_id`, `arrivee_id`) entre deux individus/entités du graphe** |
| GET | `/rgpd/candidats` | administrateur | Aperçu à blanc (dry-run) des dossiers/personnes éligibles à la purge RGPD |
| POST | `/rgpd/purge` | administrateur | Exécute la purge (anonymisation) — irréversible |

`/relations/graphe` agrège deux sources : la table `relations` (liens
personne↔personne) et la table `vehicules` (lien `proprietaire`
automatique entre une personne et ses véhicules) — c'est la "construction
automatique du graphe" mentionnée en 3.3 du cahier des charges.

`/incidents/analyse/hotspots` regroupe les incidents par cellule de grille
(taille paramétrable via `rayon_metres`, défaut 500 m) et ne retient que
les cellules avec au moins `min_incidents` (défaut 3). Il s'agit d'une
agrégation géographique rétrospective de faits déjà survenus — le cahier
des charges (6.3) exclut explicitement toute notation prédictive
d'individus, et cet endpoint ne fait qu'agréger des lieux, pas des
personnes.

`/preuves/{id}/custody` : chaque maillon inclut le hash SHA-256 du maillon
précédent (`horodatage_hash`), formant une hash-chain. La lecture recalcule
la chaîne et renvoie `chaine_intacte: false` / `alerte_rupture: true` si un
maillon a été altéré ou supprimé en base — c'est la mise en œuvre de
"Alertes en cas de rupture de chaîne de custody" (3.2).

`/relations/chemin` : parcours en largeur (BFS) sur le même graphe que
`/relations/graphe` (relations saisies + liens "propriétaire" déduits des
véhicules). Renvoie le chemin le plus court en nombre de sauts, avec les
nœuds et liens traversés (`trouve: false` si aucun chemin n'existe) —
"recherche de chemins entre deux individus ou entités" (3.3).

`/preuves/{id}/pieces-jointes` : le fichier est écrit sur disque sous un
nom généré (jamais le nom fourni par le client — protection contre le
path traversal), avec whitelist de types MIME et taille max (`STORAGE_DIR`,
`MAX_UPLOAD_MB` dans `.env`). Un hash SHA-256 est stocké à l'upload et
revérifié à chaque téléchargement ; en cas d'altération du fichier sur
disque, le téléchargement est bloqué (409) et une alerte est journalisée
— même logique d'intégrité que la chaîne de custody, dont l'ajout d'une
pièce jointe constitue d'ailleurs un maillon à part entière.

`/rgpd/purge` : anonymise (nom, prénom, date de naissance, signalement,
photo) les personnes rattachées **uniquement** à des dossiers **clos**
dont les faits dépassent `RGPD_RETENTION_DAYS` jours (3 ans par défaut).
Un dossier ouvert n'est jamais purgé ; une personne encore liée à un
dossier actif n'est pas anonymisée, même si un de ses autres dossiers est
purgeable. Les preuves, la chaîne de custody et le journal d'audit ne sont
jamais purgés (pièces de procédure / traçabilité légale). Utilisable en
tâche planifiée hors API : `python -m app.rgpd`. Voir `app/rgpd.py` pour
le détail des critères — à faire valider juridiquement avant tout usage
réel (cahier des charges 6.1).

## Journal d'audit

Chaque connexion, création, modification et consultation de donnée
sensible (fiche personne, chaîne de custody) est journalisée dans la table
`journal_audit` (email, action, ressource, date/heure, IP). Consultable via
`GET /audit` (filtres `ressource_type`, `ressource_id`, `utilisateur_email`,
`date_debut`, `date_fin`).

## Tests automatisés

```bash
pip install -r requirements-dev.txt
pytest
```

Les tests tournent sur une base SQLite temporaire dédiée (créée dans
`tests/conftest.py`, jamais `crimtrack.db` ni une base de production) et
couvrent :

- `test_auth_rbac.py` : accès refusé sans token, restrictions par rôle ;
- `test_custody.py` : intégrité de la hash-chain, détection d'une
  falsification, export CSV/PDF ;
- `test_attachments.py` : upload/téléchargement/suppression de pièces
  jointes, rejet des types MIME non autorisés, détection d'un fichier
  altéré sur disque ;
- `test_relations_chemin.py` : recherche de chemin direct/indirect/absent ;
- `test_rgpd.py` : purge RGPD (dossiers ouverts jamais purgés, personnes
  encore actives préservées, anonymisation effective sur les dossiers
  clos périmés).

À intégrer dans la CI GitHub Actions (`pytest` doit passer avant tout
merge) — pas de workflow `.github/workflows/` fourni dans ce dépôt, à
ajouter côté projet si besoin.

## Migrations de schéma (Alembic)

Le schéma est désormais versionné via Alembic (`migrations/`), avec une
révision initiale (`0001_initial_schema`) qui reproduit fidèlement le
schéma actuel. `Base.metadata.create_all()` reste appelé au démarrage de
l'app pour ne rien casser en développement local, mais **toute évolution
de schéma doit passer par une nouvelle révision Alembic**, pas par
`create_all`.

```bash
# Appliquer les migrations sur la base configurée (DATABASE_URL)
alembic upgrade head

# Après une modification de app/models.py, générer une nouvelle révision
alembic revision --autogenerate -m "description du changement"
alembic upgrade head
```

## Modèle de données

Toutes les tables du socle commun (4.1) sont modélisées dans `app/models.py` :
`incidents`, `personnes`, `vehicules`, `preuves`, `chaine_custody`,
`relations`, `lectures_anpr`, `utilisateurs`, `journal_audit`, plus les
tables de liaison `incident_personnes` / `incident_vehicules`.

## Limites connues / prochaines étapes

- Endpoints ANPR volontairement limités à l'ingestion de lectures déjà
  décodées (pas de traitement d'image/vidéo dans ce dépôt — hors périmètre
  API, cf. 3.4).
- Chiffrement au repos (4.3) : dépend de la configuration PostgreSQL/volume
  en production, non géré au niveau applicatif ici.
- Pièces jointes : stockage sur disque local (`STORAGE_DIR`) — à monter
  sur un volume persistant (ou faire évoluer vers un stockage objet type
  S3) avant un déploiement multi-instance.
- Purge RGPD : les critères de rétention (`RGPD_RETENTION_DAYS`, statuts
  "clos"/"classé sans suite") sont un point de départ technique, **pas**
  une validation juridique — cf. cahier des charges 6.1, à faire valider
  avec le service concerné avant tout usage réel.
- Pas de workflow CI (`.github/workflows/`) fourni dans ce dépôt — `pytest`
  est prêt à y être branché.

## Note importante

Ce code n'a pas pu être exécuté dans l'environnement de génération (pas
d'accès réseau pour `pip install`, y compris pour la suite de tests
`pytest`). Il suit les conventions standards FastAPI/SQLAlchemy/Alembic/
python-jose/passlib et devrait fonctionner tel quel — la syntaxe de tous
les fichiers Python a été vérifiée (`py_compile`), mais faites tourner
`pytest` et l'app en local/CI et signalez-moi toute erreur.
