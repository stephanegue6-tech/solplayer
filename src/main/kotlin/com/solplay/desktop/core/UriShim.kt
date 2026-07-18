package android.net

import java.net.URI

/**
 * Remplace android.net.Uri (utilisé par SavedPlaylist.detectXtreamCredentials
 * pour extraire scheme/host/port/username/password d'un lien M3U qui est en
 * réalité un lien Xtream déguisé). S'appuie sur java.net.URI, disponible
 * nativement sur desktop.
 */
class Uri private constructor(private val raw: String) {
    companion object {
        fun parse(url: String): Uri = Uri(url)
    }

    private val uri: URI? = try { URI(raw) } catch (e: Exception) { null }

    val scheme: String? get() = uri?.scheme
    val host: String? get() = uri?.host
    val port: Int get() = uri?.port ?: -1

    fun getQueryParameter(name: String): String? {
        val query = uri?.rawQuery ?: return null
        return query.split("&")
            .map { it.split("=", limit = 2) }
            .firstOrNull { it.getOrNull(0) == name }
            ?.getOrNull(1)
            ?.let { java.net.URLDecoder.decode(it, "UTF-8") }
    }
}
