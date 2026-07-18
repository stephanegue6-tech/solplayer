package com.solplay.desktop.core

import uk.co.caprica.vlcj.factory.discovery.NativeDiscovery
import java.awt.Desktop
import java.net.URI

/**
 * Vérifie qu'une installation locale de VLC Media Player est détectable sur
 * cette machine. vlcj (le lecteur vidéo desktop, voir PlayerScreen.kt) pilote
 * une installation VLC EXTERNE - contrairement à ExoPlayer côté Android qui
 * est autonome, vlcj ne fonctionne pas du tout sans VLC installé séparément.
 *
 * Sans cette vérification, le premier signe d'un VLC manquant serait un
 * crash obscur au moment précis de lancer une vidéo ("no vlc installation
 * found"), après que l'utilisateur ait déjà navigué jusque-là - beaucoup
 * moins clair qu'un message dès le lancement de l'app.
 */
object VlcCheck {
    const val DOWNLOAD_URL = "https://www.videolan.org/vlc/download-windows.html"

    fun isAvailable(): Boolean = try {
        NativeDiscovery().discover()
    } catch (e: Throwable) {
        false
    }
}

/**
 * Ouvre une URL dans le navigateur par défaut du système. Renvoie false si
 * l'ouverture échoue (ex: environnement sans navigateur associé) - dans ce
 * cas l'appelant doit afficher l'URL en texte sélectionnable/copiable en repli.
 */
fun openUrlInBrowser(url: String): Boolean = try {
    if (Desktop.isDesktopSupported() && Desktop.getDesktop().isSupported(Desktop.Action.BROWSE)) {
        Desktop.getDesktop().browse(URI(url))
        true
    } else {
        false
    }
} catch (e: Exception) {
    false
}
