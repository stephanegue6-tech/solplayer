package com.solplay.iptv

/** Les 3 grandes catégories affichées sous forme d'onglets dans ChannelsActivity. */
enum class ContentType {
    LIVE, MOVIE, SERIES
}

/**
 * Détermine si une chaîne est une chaîne Live, un Film (VOD) ou une Série.
 *
 * Les fournisseurs Xtream Codes structurent presque toujours l'URL du flux
 * avec "/live/", "/movie/" ou "/series/" dans le chemin : c'est le repère le
 * plus fiable. En repli (playlists M3U génériques sans cette structure), on
 * se base sur des mots-clés courants dans le nom de la catégorie (group-title).
 */
fun Channel.contentType(): ContentType {
    val url = streamUrl.lowercase()
    val group = (groupTitle ?: "").lowercase()

    return when {
        url.contains("/movie/") -> ContentType.MOVIE
        url.contains("/series/") -> ContentType.SERIES
        url.contains("/live/") -> ContentType.LIVE

        group.contains("serie") -> ContentType.SERIES
        group.contains("vod") || group.contains("film") || group.contains("movie") -> ContentType.MOVIE

        else -> ContentType.LIVE
    }
}
