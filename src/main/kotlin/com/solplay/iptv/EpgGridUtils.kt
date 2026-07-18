package com.solplay.iptv

/**
 * Construit les blocs à afficher sur une ligne de la grille EPG, à partir
 * des créneaux réels renvoyés par le panel ([XtreamApiClient.EpgSlotRaw]).
 *
 * La grille attend une frise CONTINUE (aucun trou) sur toute la fenêtre de
 * temps affichée : quand le panel n'a pas d'info pour une plage (fréquent),
 * on comble avec un bloc "Pas d'information", exactement comme le fait
 * l'app de référence de l'utilisateur (voir capture d'écran).
 */
object EpgGridUtils {

    data class Segment(
        val title: String,
        val startMillis: Long,
        val endMillis: Long,
        val isPlaceholder: Boolean
    )

    const val NO_INFO_LABEL = "Pas d'information"

    /**
     * @param programs créneaux bruts (pas forcément triés, peuvent déborder de la fenêtre)
     * @param windowStart début de la fenêtre affichée (epoch millis)
     * @param windowEnd fin de la fenêtre affichée (epoch millis)
     */
    fun buildSegments(
        programs: List<XtreamApiClient.EpgSlotRaw>,
        windowStart: Long,
        windowEnd: Long
    ): List<Segment> {
        if (windowEnd <= windowStart) return emptyList()

        val relevant = programs
            .filter { it.endMillis > windowStart && it.startMillis < windowEnd }
            .sortedBy { it.startMillis }

        val segments = mutableListOf<Segment>()
        var cursor = windowStart

        for (program in relevant) {
            val start = maxOf(program.startMillis, windowStart)
            val end = minOf(program.endMillis, windowEnd)
            // Programme déjà entièrement couvert par le précédent (chevauchement) : on l'ignore.
            if (end <= cursor) continue

            if (start > cursor) {
                segments += Segment(NO_INFO_LABEL, cursor, start, isPlaceholder = true)
            }
            segments += Segment(program.title, maxOf(start, cursor), end, isPlaceholder = false)
            cursor = end
        }

        if (cursor < windowEnd) {
            segments += Segment(NO_INFO_LABEL, cursor, windowEnd, isPlaceholder = true)
        }

        return segments
    }
}
