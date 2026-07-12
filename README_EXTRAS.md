# Extras SolPlay

## 1. Logo (solplay_logo.svg)
Fichier vectoriel (s'ouvre dans un navigateur, Figma, Illustrator, Canva...).
Utilise-le pour :
- L'icône de l'application (déjà adapté ci-dessous)
- Ton site web, tes réseaux sociaux, tes factures, etc.

## 2. Icône de l'application Android (android_icon_patch/)
Pour remplacer l'icône par défaut du projet SolPlayIPTV par ton logo :

1. Copie `ic_launcher_background.xml` et `ic_launcher_foreground.xml`
   dans `app/src/main/res/drawable/` du projet SolPlayIPTV.
2. Copie `mipmap-anydpi-v26/ic_launcher.xml` dans
   `app/src/main/res/mipmap-anydpi-v26/` (crée le dossier s'il n'existe pas).
3. Supprime les anciens fichiers `ic_launcher.png` / `ic_launcher_round.png`
   dans les dossiers `mipmap-*` s'ils existent, pour éviter les conflits.
4. Recompile l'app — la nouvelle icône orange/vert/blanc apparaîtra.

## 3. Générateur de codes de licence Pro (generate_license_codes.py)
Génère des codes d'activation valides, compatibles avec la vérification
intégrée dans l'app (TrialManager.kt).

Utilisation :
```
python3 generate_license_codes.py 20
```
→ affiche 20 codes et les enregistre dans `licenses_output.csv` avec des
colonnes pour noter le client, la date, et si le code a déjà été utilisé.

Envoie ensuite le code correspondant au client après paiement (par email à
partir de stephanegue2018@gmail.com, ou WhatsApp au +225 05 03 06 69 12),
et il l'entre dans l'écran "Activer la version Pro" de l'app.

⚠️ Rappel : ce système est local/hors-ligne, donc pratique pour démarrer
mais pas inviolable. Pour une protection plus robuste, prévois à terme une
vérification serveur (voir la note en bas du script Python).
