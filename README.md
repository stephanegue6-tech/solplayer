# SolPlay – Lecteur IPTV M3U

Application Android (Kotlin) type "Smarters Pro / IBO Player" pour la marque **SolPlay**.

## Fonctionnalités incluses
- Chargement de playlists M3U/M3U8 par URL
- Lecture des flux (ExoPlayer / Media3, compatible HLS, TS)
- Liste des chaînes avec logos et catégories
- Essai gratuit de **30 jours** géré automatiquement à la première ouverture
- Écran d'activation de la version **Pro** par code d'activation
- Charte graphique orange / blanc / vert
- Coordonnées de contact intégrées (email + téléphone)

## ⚠️ Comment compiler en .apk
Ce dossier est un projet **Android Studio** complet mais le code n'a pas pu être
compilé automatiquement dans cet environnement (pas d'accès internet pour
télécharger le SDK Android / Gradle). Pour obtenir ton .apk :

1. Installe [Android Studio](https://developer.android.com/studio) (gratuit).
2. Ouvre ce dossier `SolPlayIPTV` avec "Open an existing project".
3. Laisse Gradle synchroniser (il télécharge les dépendances automatiquement).
4. Menu **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
5. Ton fichier `.apk` sera dans `app/build/outputs/apk/debug/`.

Pour une version signée prête à publier sur Google Play, utilise
**Build > Generate Signed Bundle / APK**.

## ⚠️ Points importants avant mise en production

1. **Système de licence** : le code actuel (`TrialManager.kt`) vérifie le code
   d'activation localement (hors-ligne). C'est fonctionnel pour démarrer, mais
   un utilisateur technique peut le contourner en réinitialisant les données
   de l'app. Pour une vraie protection commerciale, il faut relier
   l'activation à un serveur (ex: Firebase Firestore ou ton propre backend)
   qui génère et vérifie les codes liés à chaque appareil.

2. **Génération des codes de licence** : pense à créer un petit outil
   (script ou page web) qui génère des codes valides selon la règle définie
   dans `validateCodeOffline()`, à envoyer par email/WhatsApp après paiement.

3. **Icône de l'application** : le projet utilise l'icône par défaut
   `@mipmap/ic_launcher`. Remplace-la par ton logo SolPlay (orange/blanc/vert)
   via Android Studio : clic droit sur `res` > New > Image Asset.

4. **Contenu diffusé** : cette application est un lecteur technique
   (comme VLC) — elle ne fournit aucune chaîne. Assure-toi que les playlists
   M3U que tes utilisateurs chargeront proviennent de sources dont tu détiens
   les droits de diffusion.

## Coordonnées SolPlay intégrées à l'app
- Email : stephanegue2018@gmail.com
- Téléphone : +225 05 03 06 69 12
