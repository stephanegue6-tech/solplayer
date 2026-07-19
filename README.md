# CrimTrack — monorepo

## Structure

```
backend/    API FastAPI (Python)
frontend/   Interface web statique (HTML/JS, sans build)
mobile/     Scaffold app mobile (Expo / React Native)
desktop/    Enveloppe Electron -> installeur Windows
.github/workflows/build-windows-desktop.yml   Compilation automatique
```

## Obtenir un installeur Windows sans rien installer vous-même

C'est le but du workflow `.github/workflows/build-windows-desktop.yml`.
Il tourne sur un serveur GitHub (runner `windows-latest`), pas sur votre
PC : GitHub compile, vous téléchargez juste le résultat.

### Étapes

1. **Poussez ce contenu sur votre repo GitHub**, en respectant la
   structure ci-dessus (`backend/`, `frontend/`, `desktop/`,
   `.github/workflows/...`). Si votre repo a déjà une autre organisation
   (ex. deux repos séparés backend/frontend), soit vous les fusionnez
   dans un seul repo, soit vous adaptez les chemins `working-directory`
   dans le fichier de workflow.

2. **Lancez le build** :
   - Manuellement : onglet **Actions** du repo GitHub → sélectionner
     *Build Windows Desktop App* → bouton **Run workflow**.
   - Ou automatiquement en créant un tag de version :
     ```bash
     git tag v0.1.0
     git push origin v0.1.0
     ```

3. **Attendez la fin du build** (5–10 minutes : installation Python,
   compilation PyInstaller, installation Node, packaging Electron).

4. **Récupérez l'installeur** :
   - Sur un lancement manuel : onglet **Actions** → le run terminé →
     section **Artifacts** en bas de page → télécharger
     `CrimTrack-installer-windows` (fichier `.zip` contenant le `.exe`).
   - Sur un lancement par tag : le `.exe` apparaît directement dans
     l'onglet **Releases** du repo.

5. **Sur votre PC Windows** : téléchargez le `.exe`, double-cliquez,
   suivez l'installeur (NSIS — comme n'importe quel logiciel Windows
   classique). Windows SmartScreen affichera probablement un avertissement
   "éditeur inconnu" la première fois (l'app n'est pas signée
   numériquement) — cliquez sur *Informations complémentaires* puis
   *Exécuter quand même*.

Une fois installé, **CrimTrack apparaît dans le menu Démarrer** comme
n'importe quelle application. Aucun terminal, aucun Python, aucun Node
requis sur votre machine : tout est à l'intérieur de l'exécutable.

## Ce que fait l'app une fois lancée

- Elle démarre un mini-serveur backend en arrière-plan (invisible),
  crée automatiquement un jeu de données de démonstration au premier
  lancement, et ouvre une fenêtre avec l'interface CrimTrack.
- Les données (base SQLite, pièces jointes, session) sont stockées dans
  `%APPDATA%\CrimTrack`, pas dans le dossier d'installation — donc
  persistantes entre les mises à jour, et propres à réinitialiser en
  supprimant simplement ce dossier.

## Limites connues de ce build desktop

- **ANPR (Module 4)** : la lecture de plaques dépend d'OpenCV/Tesseract,
  packagés dans l'exe. Si le module se révèle instable en usage réel,
  c'est le premier point à vérifier (taille de l'exe, temps de démarrage).
- **PostGIS** : le build desktop utilise SQLite (pas PostgreSQL/PostGIS),
  donc le calcul des hotspots passe par le mode de repli Python
  (`_hotspots_python` dans `backend/app/routers/incidents.py`) plutôt que
  les requêtes géospatiales natives — suffisant pour un usage mono-poste,
  pas pour un vrai déploiement multi-unités.
- **Signature de code** : l'installeur n'est pas signé (ça coûte un
  certificat payant). SmartScreen avertira à chaque nouvelle version tant
  que ce n'est pas fait.
- **Mono-utilisateur en pratique** : rien n'empêche plusieurs comptes de
  se connecter, mais la base SQLite locale n'est pas faite pour un accès
  concurrent depuis plusieurs postes — c'est un outil de démo/poste
  individuel, pas un serveur d'unité.
