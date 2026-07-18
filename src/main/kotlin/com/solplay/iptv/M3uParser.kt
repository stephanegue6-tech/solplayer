package com.solplay.iptv

import java.io.IOException
import java.io.Serializable
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException

data class Channel(
    val name: String,
    val logoUrl: String?,
    val groupTitle: String?,
    val streamUrl: String
) : Serializable

/** Exception avec un message clair destiné à être affiché directement à l'utilisateur. */
class PlaylistLoadException(message: String) : Exception(message)

/** Coupure réseau jugée transitoire (ex: "unexpected end of stream") : vaut le coup de réessayer. */
private class TransientNetworkException(message: String) : Exception(message)

object M3uParser {

    // Précompilées une seule fois (au lieu de `Regex(...)` recréé à CHAQUE ligne
    // #EXTINF dans parseStream) : sur une playlist de 50 000+ lignes, recompiler
    // le pattern à chaque itération ajoute un surcoût CPU inutile.
    private val LOGO_REGEX = Regex("tvg-logo=\"([^\"]*)\"")
    private val GROUP_REGEX = Regex("group-title=\"([^\"]*)\"")


    /**
     * Télécharge et parse une playlist M3U depuis une URL distante.
     * Le parsing se fait en streaming (ligne par ligne) pendant le téléchargement,
     * sans jamais charger tout le fichier en mémoire d'un coup : plus rapide et
     * plus léger pour les grosses playlists (10 000+ chaînes).
     *
     * Réessaie automatiquement (jusqu'à 3 tentatives) uniquement en cas de coupure
     * réseau jugée transitoire (ex: "unexpected end of stream", fréquente avec
     * certains panels IPTV qui ferment la connexion prématurément). Un vrai timeout
     * ou un serveur injoignable, en revanche, échoue immédiatement sans réessayer :
     * réessayer n'y changerait rien et ferait juste attendre l'utilisateur pour rien.
     *
     * [onRetry] est appelé avant chaque nouvelle tentative (utile pour informer
     * l'utilisateur via l'UI que ce n'est pas figé, ex: "Nouvelle tentative 2/3…").
     */
    fun fetchAndParse(playlistUrl: String, onRetry: ((attempt: Int, maxAttempts: Int) -> Unit)? = null): List<Channel> {
        val maxAttempts = 3

        for (attempt in 1..maxAttempts) {
            try {
                return fetchAndParseOnce(playlistUrl)
            } catch (e: TransientNetworkException) {
                if (attempt >= maxAttempts) {
                    throw PlaylistLoadException(
                        "Erreur réseau pendant le chargement : ${e.message}. " +
                            "La connexion a été coupée plusieurs fois de suite, le serveur est peut-être surchargé."
                    )
                }
                onRetry?.invoke(attempt + 1, maxAttempts)
                Thread.sleep(700L * attempt) // petite pause avant de réessayer
            }
        }
        throw PlaylistLoadException("Erreur réseau inconnue pendant le chargement.")
    }

    private fun fetchAndParseOnce(playlistUrl: String): List<Channel> {
        val connection = URL(playlistUrl).openConnection() as HttpURLConnection
        connection.connectTimeout = 20000   // 20s pour établir la connexion
        connection.readTimeout = 60000      // 60s pour le téléchargement/lecture
        connection.requestMethod = "GET"
        connection.instanceFollowRedirects = true
        // Empêche la réutilisation d'une connexion Keep-Alive potentiellement déjà
        // fermée côté serveur : cause fréquente de "unexpected end of stream" sur Android.
        connection.setRequestProperty("Connection", "close")
        connection.setRequestProperty(
            "User-Agent",
            "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
        )

        try {
            connection.connect()

            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                throw PlaylistLoadException(
                    "Le serveur a répondu avec une erreur (code $responseCode). " +
                        "Vérifiez le lien ou vos identifiants Xtream."
                )
            }

            return connection.inputStream.bufferedReader().use { reader ->
                parseStream(reader)
            }
        } catch (e: SocketTimeoutException) {
            // Vrai timeout : pas transitoire, inutile de réessayer automatiquement.
            throw PlaylistLoadException(
                "Le serveur met trop de temps à répondre (timeout). " +
                    "La playlist est peut-être très volumineuse ou le serveur est lent. Réessayez."
            )
        } catch (e: UnknownHostException) {
            // Serveur injoignable / DNS : réessayer immédiatement ne change rien non plus.
            throw PlaylistLoadException(
                "Impossible de joindre le serveur. Vérifiez le lien saisi et votre connexion internet."
            )
        } catch (e: PlaylistLoadException) {
            throw e
        } catch (e: IOException) {
            // Coupure générique en plein téléchargement (ex: "unexpected end of stream") :
            // souvent transitoire côté panel IPTV, celle-ci vaut le coup d'être retentée.
            throw TransientNetworkException(e.message ?: "connexion interrompue")
        } finally {
            connection.disconnect()
        }
    }

    /** Parse le contenu texte brut d'un fichier M3U/M3U8 déjà en mémoire (ex. tests). */
    fun parse(content: String): List<Channel> = parseStream(content.reader().buffered())

    /** Parse une playlist M3U/M3U8 en streaming, ligne par ligne. */
    private fun parseStream(reader: java.io.BufferedReader): List<Channel> {
        val channels = mutableListOf<Channel>()
        var currentName = ""
        var currentLogo: String? = null
        var currentGroup: String? = null

        reader.lineSequence().forEach { rawLine ->
            val line = rawLine.trim()
            when {
                line.startsWith("#EXTINF", ignoreCase = true) -> {
                    currentName = line.substringAfterLast(",").trim().ifEmpty { "Chaîne inconnue" }
                    currentLogo = LOGO_REGEX.find(line)?.groupValues?.get(1)
                    currentGroup = GROUP_REGEX.find(line)?.groupValues?.get(1)
                }
                line.isNotEmpty() && !line.startsWith("#") -> {
                    channels.add(Channel(currentName, currentLogo, currentGroup, line))
                    currentName = ""
                    currentLogo = null
                    currentGroup = null
                }
            }
        }
        return channels
    }
}
