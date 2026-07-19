# CrimTrack Mobile — scaffold

Application mobile native (Expo / React Native), point d'extension prévu
par le cahier des charges section 2.3 : *« Application mobile native (le
projet cible une interface web responsive dans un premier temps) »*.

**Ceci est un scaffold, pas une app complète.** Il pose la structure,
la navigation, l'authentification et le style pour que l'équipe puisse
enchaîner directement sur les écrans métier, sans redécider l'architecture
de base à chaque fois.

## Ce qui est inclus

- Authentification (login + refresh token) via `expo-secure-store`
  (équivalent mobile du `localStorage` utilisé par le frontend web —
  mais chiffré au repos, adapté à des identifiants d'enquêteur).
- Navigation par pile (`@react-navigation/native-stack`) avec redirection
  automatique vers l'écran de connexion si aucune session valide.
- Client API (`src/api.js`) qui parle aux **mêmes endpoints FastAPI** que
  `frontend/api.js` — aucune divergence de contrat entre web et mobile.
- Jetons de design (`src/theme/tokens.js`) copiés depuis
  `frontend/style.css` pour que l'app ne soit pas un produit visuellement
  différent de la console web.
- Trois écrans de démonstration : Connexion, Tableau de bord (incidents
  récents + accès rapides), Liste des incidents, Détail d'un incident.

## Ce qui n'est PAS inclus (volontairement, à faire ensuite)

- Carte interactive mobile (`react-native-maps` est déjà en dépendance,
  mais aucun écran ne l'utilise encore — brancher sur
  `GET /incidents/analyse/hotspots`).
- Capture photo/vidéo pour l'ANPR depuis le terminal (caméra du téléphone
  → `POST /anpr/lectures/depuis-image`).
- Mode hors-ligne / file d'attente de synchronisation, important pour un
  usage terrain en zone de couverture réseau limitée.
- Notifications push (alertes de correspondance ANPR, rupture de chaîne
  de custody).
- Polices Newsreader/Inter/IBM Plex Mono embarquées via `expo-font` (le
  scaffold utilise la police système en attendant).

## Démarrer

```bash
npm install
cp .env.example .env   # renseigner EXPO_PUBLIC_API_BASE
npx expo start
```

Nécessite l'app **Expo Go** sur le téléphone (ou un simulateur
iOS/Android) pour tester sans build natif complet.

## Sécurité

- Les jetons sont stockés via `expo-secure-store` (Keychain iOS /
  Keystore Android), jamais en clair.
- Le rôle RBAC reçu du backend (`enqueteur`, `analyste`, `opj`,
  `administrateur`) doit être utilisé pour masquer/désactiver les actions
  non autorisées, comme côté web — pas encore fait dans ce scaffold minimal.
