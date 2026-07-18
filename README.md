# SolPlay Desktop (Windows 10) — v1 (base fonctionnelle)

Port desktop de l'app Android SolPlay, en **Kotlin + Compose Desktop**, réutilisant
directement la logique métier existante (parsing M3U/Xtream, licence,
cache, synchronisation admin Firebase) plutôt que de tout réécrire.

## ✅ Ce qui est fait et fonctionnel dans cette v1

- **Fichiers 100% réutilisés tels quels** (aucune ligne modifiée) :
  `M3uParser.kt`, `Bouquet.kt`, `ContentType.kt`, `EpgGridUtils.kt`,
  `SavedPlaylist.kt`, `channelRepository.kt`, `CodeRedeemer.kt`.
- **Fichiers réutilisés avec adaptation minimale** (même logique, juste le
  "backend" Android→desktop changé via des petites couches de compatibilité) :
  `TrialManager.kt`, `DeviceKeyManager.kt`, `DevicePlaylistSync.kt`,
  `ChannelCacheStore.kt`, `XtreamApiClient.kt`, `TmdbClient.kt`,
  `UpdateChecker.kt`, `PlaylistStore.kt`.
- **Écrans desktop (Compose)** : démarrage, activation/licence (avec ta clé
  appareil + vérification auto toutes les 10s, comme sur Android), connexion
  (code / M3U / Xtream, + connexion automatique si l'admin a assigné un
  compte), liste des chaînes avec recherche/filtre, lecture vidéo (VLC).
- **Se connecte à la même base Firebase** que ton app Android et ton
  `admin_panel.html` — un client activé depuis l'admin fonctionne pour les
  deux plateformes sans rien reconfigurer.

## ⚠️ Ce qui N'EST PAS encore porté (honnêteté sur le périmètre)

L'app Android v18 est allée plus loin que ce qu'une seule session peut porter
intégralement. Pas encore fait :
- **Grille EPG** (programme TV détaillé par créneaux horaires)
- **Fiches TMDB** (affiches/synopsis films-séries) — `TmdbClient.kt` est
  porté et prêt à l'emploi, mais aucun écran ne l'utilise encore
- **Bouquets** (regroupements personnalisés de chaînes)
- **Rappel automatique du temps restant** (notification périodique — sur
  Windows, ça se ferait via la zone de notification système/system tray)
- **Écran "À propos"** et paramètres avancés

Je peux les ajouter dans une prochaine session, un par un.

## 🔧 Différences techniques assumées (Android → Windows)

| Sur Android | Sur ce port desktop |
|---|---|
| ExoPlayer/Media3 (lecture vidéo) | VLC via vlcj — **nécessite que VLC soit installé sur le PC Windows** ([gratuit ici](https://www.videolan.org/vlc/download-windows.html)) |
| SharedPreferences | Fichiers JSON dans `%APPDATA%\SolPlay\prefs\` |
| EncryptedSharedPreferences (Android Keystore) | Stockage **non chiffré** au repos (même niveau que la plupart des lecteurs IPTV desktop). Pour un vrai chiffrement, prochaine étape possible : Windows DPAPI via JNA |
| SDK Firebase Android (websocket) | API REST Firebase (HTTP), fonctionnellement équivalente pour les lectures utilisées ici |

## 🏗️ Comment compiler en .exe sur ton PC Windows 10

1. Installe [un JDK 17](https://adoptium.net/) (Temurin 17 recommandé).
2. Installe [VLC Media Player](https://www.videolan.org/vlc/download-windows.html) (nécessaire pour la lecture vidéo).
3. Ouvre un terminal (PowerShell) dans ce dossier `solplay-desktop`.
4. Génère l'exécutable/installeur :
   ```
   .\gradlew.bat packageMsi
   ```
   (Gradle télécharge tout automatiquement au premier lancement — connexion
   internet nécessaire cette première fois.)
5. Le fichier `.msi` d'installation se trouve ensuite dans :
   `build/compose/binaries/main/msi/`
6. Pour juste tester sans packager, tu peux aussi lancer directement :
   ```
   .\gradlew.bat run
   ```

**Note** : je n'ai pas pu compiler/tester ce projet moi-même (pas d'accès à
Windows ni à Gradle en ligne dans mon environnement) — il te faudra faire ce
premier build sur ta machine pour repérer d'éventuelles erreurs de
compilation restantes, et je pourrai les corriger avec toi à partir des
messages d'erreur exacts.

## 📁 Structure

```
solplay-desktop/
├── build.gradle.kts          ← config Compose Desktop, VLC, packaging Windows
├── settings.gradle.kts
└── src/main/kotlin/
    ├── com/solplay/iptv/      ← logique métier réutilisée depuis l'app Android
    └── com/solplay/desktop/
        ├── Main.kt            ← point d'entrée, navigation entre écrans
        ├── core/               ← couches de compatibilité Android→desktop
        │   ├── ContextShim.kt      (Context/SharedPreferences)
        │   ├── FirebaseShim.kt     (SDK Firebase Android → REST)
        │   ├── Log.kt              (android.util.Log + Base64)
        │   └── UriShim.kt          (android.net.Uri)
        └── ui/                 ← écrans Compose Desktop
```
