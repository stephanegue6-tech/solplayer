import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {
    kotlin("jvm") version "1.9.24"
    id("org.jetbrains.compose") version "1.6.11"
    kotlin("plugin.serialization") version "1.9.24"
}

// Numéro de version qui change à CHAQUE build sur GitHub Actions (via la
// variable GITHUB_RUN_NUMBER, fournie automatiquement par GitHub, incrémentée
// à chaque exécution du workflow - aucune configuration supplémentaire
// nécessaire côté repo).
//
// C'est important : Windows Installer (.msi) se base sur ce numéro pour
// savoir s'il doit remplacer une installation existante. S'il reste identique
// d'un build à l'autre (ex: "1.0.0" codé en dur), Windows considère souvent
// que la version "est déjà installée" et ne remplace rien du tout, même si
// le contenu a réellement changé - symptôme typique : "j'installe la
// nouvelle version mais rien ne change", alors que le nouveau code est
// pourtant bien présent dans l'installeur généré.
//
// En local (pas de CI), retombe sur "1.0.0" - si tu testes des installations
// répétées en local, augmente ce nombre à la main ou désinstalle l'ancienne
// version depuis "Applications et fonctionnalités" avant de réinstaller.
val appVersion = providers.environmentVariable("GITHUB_RUN_NUMBER")
    .map { "1.0.$it" }
    .getOrElse("1.0.0")

group = "com.solplay.desktop"
version = appVersion

repositories {
    google()
    mavenCentral()
    maven("https://maven.pkg.jetbrains.space/public/p/compose/dev")
}

dependencies {
    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    implementation(compose.materialIconsExtended)

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-swing:1.8.1")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")

    // Lecture vidéo : ExoPlayer (Android) n'existe pas sur desktop. On utilise
    // VLC via vlcj, qui pilote une installation locale de VLC (gratuite,
    // https://www.videolan.org) - lit les mêmes formats que le lecteur
    // Android (HLS, TS, MP4...), donc compatible avec les mêmes flux IPTV.
    implementation("uk.co.caprica:vlcj:4.8.2")

    // Requêtes HTTP vers Firebase REST, Xtream, TMDB, M3U - remplace les
    // appels utilisant le SDK Android Firebase (indisponible hors Android).
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.json:json:20240303")

    testImplementation(kotlin("test"))
}

// --- Génère com.solplay.iptv.BuildConfig, absent d'un projet Kotlin/JVM
// classique (contrairement à un projet Android, où c'est une classe générée
// automatiquement). TmdbClient.kt référence BuildConfig.TMDB_API_KEY tel
// quel (fichier repris sans modification depuis l'app Android) : sans cette
// génération, le module ne compile pas du tout.
//
// Valeur de la clé, par ordre de priorité :
//   1. -PtmdbApiKey=xxx sur la ligne de commande (ou dans gradle.properties en local)
//   2. variable d'environnement TMDB_API_KEY (utilisée par le workflow GitHub
//      Actions ci-dessous, elle-même alimentée par le secret de dépôt du même nom)
//   3. chaîne vide - l'app démarre quand même, simplement sans affiches TMDB
//      (TmdbClient le détecte et journalise un message clair au lieu de planter)
val generatedBuildConfigDir = layout.buildDirectory.dir("generated/solplayBuildConfig/kotlin")

val generateBuildConfig by tasks.registering {
    outputs.dir(generatedBuildConfigDir)

    doLast {
        val tmdbApiKey = ((project.findProperty("tmdbApiKey") as? String) ?: System.getenv("TMDB_API_KEY") ?: "")
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")

        val packageDir = generatedBuildConfigDir.get().asFile.resolve("com/solplay/iptv")
        packageDir.mkdirs()
        packageDir.resolve("BuildConfig.kt").writeText(
            """
            package com.solplay.iptv

            // Fichier généré automatiquement par la tâche Gradle "generateBuildConfig"
            // (voir build.gradle.kts) - NE PAS éditer à la main, et ne pas committer
            // (le dossier build/ est ignoré par git).
            object BuildConfig {
                const val TMDB_API_KEY: String = "$tmdbApiKey"
                const val VERSION_NAME: String = "${project.version}"
            }
            """.trimIndent()
        )
    }
}

kotlin {
    jvmToolchain(17)
    sourceSets["main"].kotlin.srcDir(generatedBuildConfigDir)
}

tasks.named("compileKotlin") {
    dependsOn(generateBuildConfig)
}

compose.desktop {
    application {
        mainClass = "com.solplay.desktop.MainKt"

        nativeDistributions {
            targetFormats(TargetFormat.Msi, TargetFormat.Exe)
            packageName = "SolPlay"
            packageVersion = appVersion
            windows {
                menuGroup = "SolPlay"
                // upgradeUuid figé pour que les mises à jour MSI remplacent
                // proprement l'installation précédente au lieu d'en créer une seconde.
                upgradeUuid = "8f2c9b3a-6e2d-4a1b-9c3e-1d7f5a2b8e40"
                // Icône de l'app (identique à celle de la version Android),
                // convertie en .ico multi-résolutions (16 à 256px) à partir du
                // logo source. Utilisée pour l'exécutable, le raccourci du
                // menu Démarrer, et l'installeur .msi lui-même.
                iconFile.set(project.file("src/main/resources/solplay.ico"))
            }
        }
    }
}
