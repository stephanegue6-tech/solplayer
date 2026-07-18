package com.solplay.iptv

import java.io.Serializable
import java.util.UUID

/** Type de connexion d'une playlist enregistrée. */
enum class PlaylistMode { M3U, XTREAM }

/**
 * Une playlist enregistrée localement sur l'appareil : soit ajoutée
 * manuellement par l'utilisateur, soit obtenue via un code fourni par
 * l'administrateur (voir CodeRedeemer / champ fromCode).
 */
data class SavedPlaylist(
    val id: String = UUID.randomUUID().toString(),
    var name: String,
    var mode: PlaylistMode,
    var m3uUrl: String = "",
    var xtreamServer: String = "",
    var xtreamUsername: String = "",
    var xtreamPassword: String = "",
    var fromCode: String? = null
) : Serializable {

    companion object {
        /**
         * Beaucoup de fournisseurs IPTV distribuent en réalité un lien Xtream
         * déguisé en "lien M3U" (`http://serveur:port/get.php?username=U&password=P&...`).
         * Si l'utilisateur colle un tel lien dans l'onglet "Lien M3U", on veut
         * quand même bénéficier des enrichissements réservés au mode Xtream
         * (catégories, logos, EPG "en cours", détection d'expiration) - on
         * détecte donc ce cas et on extrait serveur/user/password.
         *
         * Renvoie null si l'URL ne correspond pas à ce format (M3U générique
         * sans username/password identifiables).
         */
        fun detectXtreamCredentials(url: String): Triple<String, String, String>? {
            return try {
                val uri = android.net.Uri.parse(url.trim())
                val user = uri.getQueryParameter("username")?.trim()
                val pass = uri.getQueryParameter("password")?.trim()
                val scheme = uri.scheme
                val host = uri.host
                if (user.isNullOrEmpty() || pass.isNullOrEmpty() || scheme.isNullOrEmpty() || host.isNullOrEmpty()) {
                    return null
                }
                val port = uri.port
                val server = if (port > 0) "$scheme://$host:$port" else "$scheme://$host"
                Triple(server, user, pass)
            } catch (e: Exception) {
                null
            }
        }
    }

    /** Construit l'URL effective de la playlist selon le mode choisi. */
    fun buildUrl(): String {
        return if (mode == PlaylistMode.XTREAM) {
            val server = xtreamServer.trim().trimEnd('/')
            "$server/get.php?username=$xtreamUsername&password=$xtreamPassword&type=m3u_plus&output=ts"
        } else {
            m3uUrl.trim()
        }
    }

    /**
     * Identifiants Xtream (serveur, utilisateur, mot de passe) permettant
     * d'interroger l'API `player_api.php` du panel (utilisée notamment pour
     * détecter l'expiration de l'abonnement, voir XtreamApiClient.checkAccountStatus).
     *
     * - En mode XTREAM : renvoie directement les champs saisis.
     * - En mode M3U : de nombreux fournisseurs génèrent en réalité un lien
     *   de type "http://serveur:port/get.php?username=U&password=P&type=m3u...",
     *   qui est un lien Xtream déguisé. On tente donc d'en extraire les
     *   identifiants ; si le lien ne correspond pas à ce format (M3U "générique"
     *   sans username/password), on renvoie null (aucune vérification possible).
     */
    fun extractXtreamCredentials(): Triple<String, String, String>? {
        if (mode == PlaylistMode.XTREAM) {
            val server = xtreamServer.trim().trimEnd('/')
            val user = xtreamUsername.trim()
            val pass = xtreamPassword.trim()
            if (server.isEmpty() || user.isEmpty() || pass.isEmpty()) return null
            return Triple(server, user, pass)
        }

        return detectXtreamCredentials(m3uUrl)
    }
}
