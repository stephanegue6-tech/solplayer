# Configuration Firebase pour SolPlay

L'app utilise désormais Firebase Realtime Database pour activer les licences
Pro à distance. Comme c'est ton propre projet Firebase (gratuit), il faut le
créer toi-même — je ne peux pas le faire à ta place, c'est lié à ton compte
Google personnel.

## 1. Créer le projet Firebase (5 minutes, gratuit)

1. Va sur https://console.firebase.google.com
2. Clique "Ajouter un projet" → nomme-le "SolPlay" → suis les étapes (tu peux
   désactiver Google Analytics, pas nécessaire)
3. Une fois le projet créé, clique sur l'icône Android pour "Ajouter une app" :
   - Nom du package : `com.solplay.iptv` (exactement celui-ci, obligatoire)
   - Télécharge le fichier **`google-services.json`** proposé
4. Place ce fichier téléchargé directement dans le dossier `app/` de ton
   projet SolPlayIPTV (au même niveau que `build.gradle` du module app),
   puis upload-le sur ton dépôt GitHub au même endroit

## 2. Activer Realtime Database

1. Dans le menu de gauche Firebase, clique "Realtime Database" → "Créer une
   base de données"
2. Choisis une région proche de toi (Europe recommandé)
3. Démarre en **mode test** (on sécurisera juste après)
4. Une fois créée, va dans l'onglet "Règles" et remplace par :

```json
{
  "rules": {
    "licenses": {
      "$deviceKey": {
        "active": {
          ".read": true
        },
        ".write": "auth != null"
      }
    }
  }
}
```

Ça veut dire : n'importe qui peut vérifier si SA propre clé est activée
(lecture), mais seul un administrateur connecté peut modifier une licence
(écriture).

## 3. Créer ton compte administrateur

1. Dans Firebase, va dans "Authentication" → "Get started"
2. Onglet "Sign-in method" → active "E-mail/Mot de passe"
3. Onglet "Users" → "Add user" → crée ton compte admin (email + mot de passe)
   — c'est ce compte qui te servira à te connecter au panneau admin

## 4. Configurer le panneau admin (admin_panel.html)

1. Ouvre le fichier `admin_panel.html` (fourni séparément) avec un éditeur
   de texte
2. Dans Firebase, va dans "Paramètres du projet" (roue crantée) → fais
   défiler jusqu'à "Vos applications" → clique sur l'app Web (ou crée-en une
   avec l'icône `</>` si elle n'existe pas) → copie le bloc `firebaseConfig`
3. Colle ce bloc dans `admin_panel.html` à l'endroit indiqué
   (`// COLLE TA CONFIGURATION FIREBASE ICI`)
4. Ouvre ce fichier HTML dans un navigateur (double-clic dessus, ou héberge-le
   sur GitHub Pages/Netlify pour y accéder de partout) → connecte-toi avec
   ton compte admin créé à l'étape 3

## 5. Comment ça fonctionne pour toi au quotidien

1. Un client t'envoie sa "clé appareil" (visible dans l'app, écran
   d'activation, avec un bouton "Copier")
2. Il te paie (comme tu veux : Mobile Money, virement...)
3. Tu ouvres ton panneau admin, colles sa clé appareil, remplis son nom/email
   si tu veux, et actives sa licence
4. Le client clique sur "Vérifier mon activation" dans l'app → accès Pro
   débloqué immédiatement (il doit juste être connecté à internet à ce
   moment précis, ensuite l'app fonctionne aussi hors-ligne)

## Important
- Le fichier `google-services.json` contient des clés spécifiques à TON
  projet Firebase — ne le partage pas publiquement si tu préfères, même si
  ce n'est pas un secret critique en soi (les vraies règles de sécurité sont
  dans les "Règles" de la base de données, pas dans ce fichier).
- Le plan gratuit Firebase (Spark) est largement suffisant pour démarrer.
