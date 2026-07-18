package com.solplay.iptv

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Certains panels Xtream ne renseignent pas (ou très partiellement) l'attribut
 * `group-title` dans le fichier M3U (`get.php?...&type=m3u_plus`) pour les
 * entrées Films/Séries, alors que ce même panel connaît parfaitement la
 * catégorie de chaque contenu via son API JSON native (`player_api.php`).
 * Résultat concret côté app : la colonne "bouquets" reste vide à part
 * "Tous", puisqu'on ne peut grouper que sur un champ qui n'existe pas.
 *
 * Ce client interroge cette API JSON (get_vod_categories/get_vod_streams et
 * get_live_categories/get_live_streams) pour reconstituer une correspondance
 * fiable stream_id -> nom de catégorie, qu'on utilise ensuite pour compléter
 * (jamais écraser une valeur déjà présente et non vide) le group-title
 * manquant des chaînes obtenues via le M3U.
 *
 * Best effort : toute erreur réseau/JSON est avalée silencieusement (retourne
 * une map vide) pour ne jamais empêcher le chargement de la playlist -
 * seule la catégorisation en pâtit, pas la lecture des chaînes.
 */
object XtreamApiClient {

    private const val TAG = "XtreamApiClient"

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    /** Catégorie + logo (icône) connus par le panel pour un stream_id donné. */
    data class StreamInfo(val categoryName: String?, val logoUrl: String?)

    /** stream_id (VOD ou Live, selon [kind]) -> nom de catégorie. Conservé pour compat. */
    suspend fun fetchCategoryMap(playlist: SavedPlaylist, kind: Kind): Map<Int, String> =
        fetchStreamInfoMap(playlist, kind).mapNotNull { (id, info) ->
            info.categoryName?.let { id to it }
        }.toMap()

    /**
     * stream_id (VOD ou Live, selon [kind]) -> catégorie + logo connus par
     * l'API JSON native du panel (`player_api.php`). Contrairement au fichier
     * M3U (`get.php?...type=m3u_plus`), qui omet parfois `group-title` et/ou
     * `tvg-logo` selon les panels, l'API `get_live_streams` / `get_vod_streams`
     * renvoie presque toujours `category_id` et `stream_icon` pour chaque
     * chaîne/film - on s'en sert donc pour compléter ce qui manque côté M3U.
     */
    suspend fun fetchStreamInfoMap(playlist: SavedPlaylist, kind: Kind): Map<Int, StreamInfo> {
        if (playlist.mode != PlaylistMode.XTREAM) return emptyMap()

        return withContext(Dispatchers.IO) {
            try {
                val base = playlist.xtreamServer.trim().trimEnd('/')
                val user = playlist.xtreamUsername.trim()
                val pass = playlist.xtreamPassword.trim()
                if (base.isEmpty() || user.isEmpty() || pass.isEmpty()) return@withContext emptyMap()

                // Les deux appels sont indépendants : on les lance en parallèle au lieu
                // d'attendre le premier avant de démarrer le second (gain notable sur
                // un serveur qui met une seconde ou plus à répondre à chaque requête).
                val categoriesDeferred = async {
                    fetchJsonArray("$base/player_api.php?username=$user&password=$pass&action=${kind.categoriesAction}")
                }
                val streamsDeferred = async {
                    fetchJsonArray("$base/player_api.php?username=$user&password=$pass&action=${kind.streamsAction}")
                }

                val categories = categoriesDeferred.await() ?: return@withContext emptyMap()
                val streams = streamsDeferred.await() ?: return@withContext emptyMap()

                val categoryNames = mutableMapOf<String, String>()
                for (i in 0 until categories.length()) {
                    val c = categories.optJSONObject(i) ?: continue
                    val id = c.optString("category_id")
                    val name = c.optString("category_name")
                    if (id.isNotEmpty() && name.isNotEmpty()) categoryNames[id] = name
                }

                val result = mutableMapOf<Int, StreamInfo>()
                for (i in 0 until streams.length()) {
                    val s = streams.optJSONObject(i) ?: continue
                    val streamId = s.optInt("stream_id", -1)
                    if (streamId <= 0) continue
                    val categoryId = s.optString("category_id")
                    val categoryName = categoryNames[categoryId]
                    val logoUrl = s.optString("stream_icon").takeIf { it.isNotBlank() }
                    if (categoryName != null || logoUrl != null) {
                        result[streamId] = StreamInfo(categoryName, logoUrl)
                    }
                }
                result
            } catch (e: Exception) {
                Log.w(TAG, "Échec récupération des infos Xtream (${kind.name}) : ${e.message}")
                emptyMap()
            }
        }
    }

    /**
     * Masque les paramètres `username` et `password` d'une URL avant tout
     * envoi vers Logcat. Ex: ".../player_api.php?username=john&password=secret123"
     * devient ".../player_api.php?username=***&password=***". Les vrais
     * appels réseau utilisent toujours l'URL originale non modifiée ; seule
     * la version passée à Log.w() doit être masquée.
     */
    private fun redactCredentials(url: String): String =
        url.replace(Regex("(?<=username=)[^&]*"), "***")
            .replace(Regex("(?<=password=)[^&]*"), "***")

    private fun fetchJsonArray(url: String): JSONArray? {
        val request = Request.Builder().url(url).get().build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                Log.w(TAG, "HTTP ${response.code} pour ${redactCredentials(url)}")
                return null
            }
            val body = response.body?.string().orEmpty()
            return try {
                JSONArray(body)
            } catch (e: Exception) {
                Log.w(TAG, "Réponse JSON inattendue pour ${redactCredentials(url)} : ${e.message}")
                null
            }
        }
    }

    /** Extrait le stream_id final d'une URL Xtream (.../movie/user/pass/12345.mp4 -> 12345). */
    fun extractStreamId(streamUrl: String): Int {
        val lastSegment = streamUrl.substringAfterLast('/')
        val withoutExtension = lastSegment.substringBeforeLast('.')
        return withoutExtension.toIntOrNull() ?: -1
    }

    // ------------------------------------------------------------------
    // Chargement DIRECT via l'API JSON (sans jamais télécharger le M3U).
    //
    // Certains panels bloquent ou limitent volontairement le téléchargement
    // du fichier M3U complet (get.php) - souvent pour limiter le partage de
    // comptes - alors que l'API JSON native (player_api.php), utilisée par
    // les vrais lecteurs Xtream (TiviMate, IPTV Smarters...), continue de
    // fonctionner normalement. Ces fonctions reconstruisent directement les
    // chaînes/films depuis cette API, sans jamais passer par le M3U.
    //
    // Les Séries sont chargées en 2 temps, comme le font ces mêmes apps :
    // d'abord la liste des séries (légère), puis les épisodes d'UNE série
    // seulement au moment où l'utilisateur l'ouvre (fetchSeriesEpisodes) -
    // il serait bien trop long de récupérer les épisodes de toutes les
    // séries d'un coup (un appel réseau par série).
    // ------------------------------------------------------------------

    data class DirectLoadResult(val channels: List<Channel>, val liveCount: Int, val vodCount: Int, val seriesCount: Int)

    /** Charge Live + Films + liste des séries (sans épisodes) en parallèle, sans jamais toucher au M3U. */
    suspend fun fetchAllChannelsDirect(playlist: SavedPlaylist): DirectLoadResult = coroutineScope {
        val liveDeferred = async { fetchLiveChannelsDirect(playlist) }
        val vodDeferred = async { fetchVodChannelsDirect(playlist) }
        val seriesDeferred = async { fetchSeriesShellChannels(playlist) }

        val live = liveDeferred.await()
        val vod = vodDeferred.await()
        val series = seriesDeferred.await()

        DirectLoadResult(live + vod + series, live.size, vod.size, series.size)
    }

    private fun fetchJsonObject(url: String): JSONObject? {
        val request = Request.Builder().url(url).get().build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                Log.w(TAG, "HTTP ${response.code} pour ${redactCredentials(url)}")
                return null
            }
            val body = response.body?.string().orEmpty()
            return try {
                JSONObject(body)
            } catch (e: Exception) {
                Log.w(TAG, "Réponse JSON inattendue pour ${redactCredentials(url)} : ${e.message}")
                null
            }
        }
    }

    suspend fun fetchLiveChannelsDirect(playlist: SavedPlaylist): List<Channel> = withContext(Dispatchers.IO) {
        try {
            val (base, user, pass) = playlist.extractXtreamCredentials() ?: return@withContext emptyList()

            val categoriesDeferred = async { fetchJsonArray("$base/player_api.php?username=$user&password=$pass&action=get_live_categories") }
            val streamsDeferred = async { fetchJsonArray("$base/player_api.php?username=$user&password=$pass&action=get_live_streams") }
            val categories = categoriesDeferred.await() ?: JSONArray()
            val streams = streamsDeferred.await() ?: return@withContext emptyList()

            val categoryNames = mutableMapOf<String, String>()
            for (i in 0 until categories.length()) {
                val c = categories.optJSONObject(i) ?: continue
                val id = c.optString("category_id")
                val name = c.optString("category_name")
                if (id.isNotEmpty() && name.isNotEmpty()) categoryNames[id] = name
            }

            (0 until streams.length()).mapNotNull { i ->
                val s = streams.optJSONObject(i) ?: return@mapNotNull null
                val streamId = s.optInt("stream_id", -1)
                if (streamId <= 0) return@mapNotNull null
                val name = s.optString("name").ifBlank { "Chaîne $streamId" }
                val logo = s.optString("stream_icon").takeIf { it.isNotBlank() }
                val group = categoryNames[s.optString("category_id")]
                Channel(
                    name = name,
                    logoUrl = logo,
                    groupTitle = group,
                    streamUrl = "$base/live/$user/$pass/$streamId.ts"
                )
            }
        } catch (e: Exception) {
            Log.w(TAG, "Échec chargement direct Live : ${e.message}")
            emptyList()
        }
    }

    suspend fun fetchVodChannelsDirect(playlist: SavedPlaylist): List<Channel> = withContext(Dispatchers.IO) {
        try {
            val (base, user, pass) = playlist.extractXtreamCredentials() ?: return@withContext emptyList()

            val categoriesDeferred = async { fetchJsonArray("$base/player_api.php?username=$user&password=$pass&action=get_vod_categories") }
            val streamsDeferred = async { fetchJsonArray("$base/player_api.php?username=$user&password=$pass&action=get_vod_streams") }
            val categories = categoriesDeferred.await() ?: JSONArray()
            val streams = streamsDeferred.await() ?: return@withContext emptyList()

            val categoryNames = mutableMapOf<String, String>()
            for (i in 0 until categories.length()) {
                val c = categories.optJSONObject(i) ?: continue
                val id = c.optString("category_id")
                val name = c.optString("category_name")
                if (id.isNotEmpty() && name.isNotEmpty()) categoryNames[id] = name
            }

            (0 until streams.length()).mapNotNull { i ->
                val s = streams.optJSONObject(i) ?: return@mapNotNull null
                val streamId = s.optInt("stream_id", -1)
                if (streamId <= 0) return@mapNotNull null
                val name = s.optString("name").ifBlank { "Film $streamId" }
                val logo = s.optString("stream_icon").takeIf { it.isNotBlank() }
                val group = categoryNames[s.optString("category_id")]
                val ext = s.optString("container_extension").ifBlank { "mp4" }
                Channel(
                    name = name,
                    logoUrl = logo,
                    groupTitle = group,
                    streamUrl = "$base/movie/$user/$pass/$streamId.$ext"
                )
            }
        } catch (e: Exception) {
            Log.w(TAG, "Échec chargement direct VOD : ${e.message}")
            emptyList()
        }
    }

    /**
     * Liste des séries SANS leurs épisodes (appel léger). Chaque entrée est une
     * "coquille" reconnaissable à son streamUrl sans extension de fichier
     * (".../series/user/pass/123" au lieu de "...123.mkv") : voir
     * [ChannelsActivity.openPlayer] qui détecte ce cas pour charger les
     * épisodes réels via [fetchSeriesEpisodes] au moment où l'utilisateur
     * ouvre cette série, plutôt que de tout charger d'un coup.
     */
    suspend fun fetchSeriesShellChannels(playlist: SavedPlaylist): List<Channel> = withContext(Dispatchers.IO) {
        try {
            val (base, user, pass) = playlist.extractXtreamCredentials() ?: return@withContext emptyList()

            val categoriesDeferred = async { fetchJsonArray("$base/player_api.php?username=$user&password=$pass&action=get_series_categories") }
            val seriesDeferred = async { fetchJsonArray("$base/player_api.php?username=$user&password=$pass&action=get_series") }
            val categories = categoriesDeferred.await() ?: JSONArray()
            val seriesList = seriesDeferred.await() ?: return@withContext emptyList()

            val categoryNames = mutableMapOf<String, String>()
            for (i in 0 until categories.length()) {
                val c = categories.optJSONObject(i) ?: continue
                val id = c.optString("category_id")
                val name = c.optString("category_name")
                if (id.isNotEmpty() && name.isNotEmpty()) categoryNames[id] = name
            }

            (0 until seriesList.length()).mapNotNull { i ->
                val s = seriesList.optJSONObject(i) ?: return@mapNotNull null
                val seriesId = s.optInt("series_id", -1)
                if (seriesId <= 0) return@mapNotNull null
                val name = s.optString("name").ifBlank { "Série $seriesId" }
                val logo = s.optString("cover").takeIf { it.isNotBlank() }
                val group = categoryNames[s.optString("category_id")]
                Channel(
                    name = name,
                    logoUrl = logo,
                    groupTitle = group,
                    streamUrl = "$base/series/$user/$pass/$seriesId" // pas d'extension = coquille (voir doc ci-dessus)
                )
            }
        } catch (e: Exception) {
            Log.w(TAG, "Échec chargement direct Séries : ${e.message}")
            emptyList()
        }
    }

    /** Une chaîne "coquille" créée par [fetchSeriesShellChannels] a un streamUrl sans extension de fichier. */
    fun isSeriesShell(channel: Channel): Boolean =
        channel.contentType() == ContentType.SERIES && !channel.streamUrl.substringAfterLast('/').contains('.')

    /**
     * Récupère les épisodes réels d'UNE série (saisons + épisodes), au moment
     * où l'utilisateur l'ouvre. Chaque épisode devient un [Channel] directement
     * lisible, dans l'ordre saison/épisode.
     */
    suspend fun fetchSeriesEpisodes(playlist: SavedPlaylist, seriesChannel: Channel): List<Channel> = withContext(Dispatchers.IO) {
        try {
            val (base, user, pass) = playlist.extractXtreamCredentials() ?: return@withContext emptyList()
            val seriesId = extractStreamId(seriesChannel.streamUrl)
            if (seriesId <= 0) return@withContext emptyList()

            val info = fetchJsonObject("$base/player_api.php?username=$user&password=$pass&action=get_series_info&series_id=$seriesId")
                ?: return@withContext emptyList()
            val episodesBySeason = info.optJSONObject("episodes") ?: return@withContext emptyList()

            val result = mutableListOf<Channel>()
            val seasonKeys = episodesBySeason.keys().asSequence().sortedBy { it.toIntOrNull() ?: 0 }
            for (seasonKey in seasonKeys) {
                val episodes = episodesBySeason.optJSONArray(seasonKey) ?: continue
                for (i in 0 until episodes.length()) {
                    val ep = episodes.optJSONObject(i) ?: continue
                    val episodeId = ep.optString("id").toIntOrNull() ?: continue
                    val epNum = ep.optString("episode_num").ifBlank { "?" }
                    val title = ep.optString("title").ifBlank { "Épisode $epNum" }
                    val ext = ep.optString("container_extension").ifBlank { "mp4" }
                    result.add(
                        Channel(
                            name = "S$seasonKey · E$epNum - $title",
                            logoUrl = seriesChannel.logoUrl,
                            groupTitle = seriesChannel.groupTitle,
                            streamUrl = "$base/series/$user/$pass/$episodeId.$ext"
                        )
                    )
                }
            }
            result
        } catch (e: Exception) {
            Log.w(TAG, "Échec récupération épisodes série : ${e.message}")
            emptyList()
        }
    }

    /**
     * Complète le group-title (catégorie) des chaînes quand le M3U du panel
     * Xtream ne le fournit pas, en s'appuyant sur l'API JSON native du panel
     * (get_vod_categories / get_live_categories). Ne touche jamais un
     * group-title déjà présent - best effort : si l'appel échoue, on garde
     * les chaînes telles quelles (jamais bloquant pour le chargement).
     *
     * Seuls les Films (VOD) et le Live sont couverts pour l'instant : les
     * Séries listent des épisodes individuels dont l'identifiant dans le M3U
     * ne correspond pas au series_id de l'API.
     */
    suspend fun enrichChannelsWithCategories(playlist: SavedPlaylist, channels: List<Channel>): List<Channel> {
        if (playlist.mode != PlaylistMode.XTREAM) return channels

        // On regarde s'il manque au moins une catégorie OU un logo (pas
        // seulement la catégorie comme avant) : beaucoup de panels omettent
        // le tvg-logo dans le M3U des chaînes Live alors que l'API JSON
        // native (get_live_streams) le connaît via stream_icon.
        val needsVod = channels.any {
            it.contentType() == ContentType.MOVIE && (it.groupTitle.isNullOrBlank() || it.logoUrl.isNullOrBlank())
        }
        val needsLive = channels.any {
            it.contentType() == ContentType.LIVE && (it.groupTitle.isNullOrBlank() || it.logoUrl.isNullOrBlank())
        }
        if (!needsVod && !needsLive) return channels

        // Indépendants l'un de l'autre : lancés en parallèle plutôt que d'attendre
        // la fin du premier avant de démarrer le second.
        val vodMap: Map<Int, StreamInfo>
        val liveMap: Map<Int, StreamInfo>
        coroutineScope {
            val vodDeferred = async { if (needsVod) fetchStreamInfoMap(playlist, Kind.VOD) else emptyMap() }
            val liveDeferred = async { if (needsLive) fetchStreamInfoMap(playlist, Kind.LIVE) else emptyMap() }
            vodMap = vodDeferred.await()
            liveMap = liveDeferred.await()
        }
        if (vodMap.isEmpty() && liveMap.isEmpty()) return channels

        return channels.map { channel ->
            val map = when (channel.contentType()) {
                ContentType.MOVIE -> vodMap
                ContentType.LIVE -> liveMap
                else -> return@map channel
            }
            val info = map[extractStreamId(channel.streamUrl)] ?: return@map channel
            channel.copy(
                groupTitle = channel.groupTitle.takeUnless { it.isNullOrBlank() } ?: info.categoryName ?: channel.groupTitle,
                logoUrl = channel.logoUrl.takeUnless { it.isNullOrBlank() } ?: info.logoUrl ?: channel.logoUrl
            )
        }
    }

    enum class Kind(val categoriesAction: String, val streamsAction: String) {
        VOD("get_vod_categories", "get_vod_streams"),
        LIVE("get_live_categories", "get_live_streams")
    }

    /** Programme en cours (ou à venir) pour une chaîne Live. */
    data class EpgProgram(val title: String, val startTime: String, val endTime: String)

    private val epgCache = java.util.Collections.synchronizedMap(mutableMapOf<String, EpgProgram?>())

    /**
     * Récupère le programme en cours pour une chaîne Live via l'API EPG native
     * du panel Xtream (`get_short_epg`). Résultat mis en cache mémoire (clé
     * serveur+stream_id) le temps de la session, pour éviter de re-solliciter
     * le serveur à chaque scroll/re-bind de la RecyclerView.
     *
     * Best effort : renvoie null si le panel ne fournit pas d'EPG pour cette
     * chaîne (fréquent - beaucoup de chaînes n'ont simplement pas de données
     * EPG côté fournisseur), en cas d'erreur réseau, ou hors mode Xtream.
     */
    suspend fun fetchNowPlaying(playlist: SavedPlaylist, streamId: Int): EpgProgram? {
        if (streamId <= 0) return null
        val (base, user, pass) = playlist.extractXtreamCredentials() ?: return null

        val cacheKey = "$base|$user|$streamId"
        if (epgCache.containsKey(cacheKey)) return epgCache[cacheKey]

        return withContext(Dispatchers.IO) {
            val result = try {
                val url = "$base/player_api.php?username=$user&password=$pass&action=get_short_epg&stream_id=$streamId&limit=1"
                val request = Request.Builder().url(url).get().build()
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use null
                    val body = response.body?.string().orEmpty()
                    val listings = JSONObject(body).optJSONArray("epg_listings") ?: return@use null
                    if (listings.length() == 0) return@use null
                    val first = listings.getJSONObject(0)
                    val title = decodeEpgText(first.optString("title"))
                    if (title.isBlank()) return@use null
                    EpgProgram(
                        title = title,
                        startTime = formatEpgTime(first.optString("start")),
                        endTime = formatEpgTime(first.optString("stop", first.optString("end")))
                    )
                }
            } catch (e: Exception) {
                Log.w(TAG, "Échec EPG stream_id=$streamId : ${e.message}")
                null
            }
            epgCache[cacheKey] = result
            result
        }
    }

    /** Le panel Xtream encode généralement titre/description EPG en Base64. */
    private fun decodeEpgText(value: String): String {
        if (value.isBlank()) return ""
        return try {
            String(android.util.Base64.decode(value, android.util.Base64.DEFAULT), Charsets.UTF_8).trim()
        } catch (e: Exception) {
            value.trim()
        }
    }

    private val guideCache = java.util.Collections.synchronizedMap(mutableMapOf<String, List<EpgProgram>>())

    /**
     * Récupère le programme complet à venir (pas seulement l'émission en
     * cours) pour une chaîne Live, via `get_short_epg` avec une [limit] plus
     * grande. C'est ce qui alimente la boîte de dialogue "Programme TV"
     * ouverte en appui long sur une chaîne - contrairement à [fetchNowPlaying]
     * qui n'affiche qu'une ligne dans la liste.
     *
     * Ne remplace pas une grille multi-chaînes façon zappeur (comme dans
     * IPTV Smarters) : ça resterait à construire comme un écran à part
     * entière (grille avec défilement horizontal synchronisé sur toutes les
     * chaînes). Ici, c'est le programme d'UNE chaîne, dans l'ordre chronologique.
     *
     * Best effort : liste vide si le panel ne fournit pas d'EPG pour cette
     * chaîne, en cas d'erreur réseau, ou hors mode Xtream.
     */
    suspend fun fetchProgramGuide(playlist: SavedPlaylist, streamId: Int, limit: Int = 20): List<EpgProgram> {
        if (streamId <= 0) return emptyList()
        val (base, user, pass) = playlist.extractXtreamCredentials() ?: return emptyList()

        val cacheKey = "$base|$user|$streamId|$limit"
        guideCache[cacheKey]?.let { return it }

        return withContext(Dispatchers.IO) {
            val result = try {
                val url = "$base/player_api.php?username=$user&password=$pass&action=get_short_epg&stream_id=$streamId&limit=$limit"
                val request = Request.Builder().url(url).get().build()
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use emptyList()
                    val body = response.body?.string().orEmpty()
                    val listings = JSONObject(body).optJSONArray("epg_listings") ?: return@use emptyList()
                    (0 until listings.length()).mapNotNull { i ->
                        val item = listings.optJSONObject(i) ?: return@mapNotNull null
                        val title = decodeEpgText(item.optString("title"))
                        if (title.isBlank()) return@mapNotNull null
                        EpgProgram(
                            title = title,
                            startTime = formatEpgTime(item.optString("start")),
                            endTime = formatEpgTime(item.optString("stop", item.optString("end")))
                        )
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Échec programme complet stream_id=$streamId : ${e.message}")
                emptyList()
            }
            guideCache[cacheKey] = result
            result
        }
    }

    /** "2026-07-15 20:00:00" -> "20:00". */
    private fun formatEpgTime(raw: String): String {
        val timePart = raw.substringAfter(' ', missingDelimiterValue = raw)
        return timePart.take(5).ifEmpty { raw }
    }

    /** Une émission avec ses horaires en epoch millis (nécessaire pour positionner les blocs de la grille EPG). */
    data class EpgSlotRaw(val title: String, val startMillis: Long, val endMillis: Long)

    private val slotsCache = java.util.Collections.synchronizedMap(mutableMapOf<String, List<EpgSlotRaw>>())

    /**
     * Version "brute" (avec timestamps réels) de [fetchProgramGuide], utilisée
     * par la grille EPG multi-chaînes (EpgGridActivity) pour calculer la
     * largeur et la position de chaque bloc de programme sur la frise horaire
     * commune. [fetchProgramGuide]/[fetchNowPlaying] ne gardent que "HH:mm"
     * formaté, insuffisant ici (on a besoin de savoir *quel jour* aussi).
     */
    suspend fun fetchProgramSlotsRaw(playlist: SavedPlaylist, streamId: Int, limit: Int = 30): List<EpgSlotRaw> {
        if (streamId <= 0) return emptyList()
        val (base, user, pass) = playlist.extractXtreamCredentials() ?: return emptyList()

        val cacheKey = "$base|$user|$streamId|slots|$limit"
        slotsCache[cacheKey]?.let { return it }

        return withContext(Dispatchers.IO) {
            val result = try {
                val url = "$base/player_api.php?username=$user&password=$pass&action=get_short_epg&stream_id=$streamId&limit=$limit"
                val request = Request.Builder().url(url).get().build()
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use emptyList()
                    val body = response.body?.string().orEmpty()
                    val listings = JSONObject(body).optJSONArray("epg_listings") ?: return@use emptyList()
                    (0 until listings.length()).mapNotNull { i ->
                        val item = listings.optJSONObject(i) ?: return@mapNotNull null
                        val title = decodeEpgText(item.optString("title"))
                        if (title.isBlank()) return@mapNotNull null
                        val start = parseEpgMillis(item.optString("start")) ?: return@mapNotNull null
                        val end = parseEpgMillis(item.optString("stop", item.optString("end"))) ?: return@mapNotNull null
                        if (end <= start) return@mapNotNull null
                        EpgSlotRaw(title, start, end)
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Échec récupération créneaux EPG stream_id=$streamId : ${e.message}")
                emptyList()
            }
            slotsCache[cacheKey] = result
            result
        }
    }

    /** Parse un horodatage EPG Xtream ("yyyy-MM-dd HH:mm:ss") en epoch millis. */
    private fun parseEpgMillis(raw: String): Long? {
        if (raw.isBlank()) return null
        return try {
            val sdf = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US)
            sdf.parse(raw)?.time
        } catch (e: Exception) {
            null
        }
    }

    /** Résultat de la vérification du statut d'un abonnement Xtream. */
    data class AccountStatus(
        val expired: Boolean,
        /** Statut brut renvoyé par le panel ("Active", "Expired", "Banned", "Disabled"...). */
        val statusLabel: String?,
        /** Date d'expiration en millisecondes (epoch), null si non fournie/illimitée. */
        val expiresAtMillis: Long?
    )

    /**
     * Interroge l'API native du panel Xtream (`player_api.php`, sans paramètre
     * `action`) pour connaître le statut réel de l'abonnement : actif, expiré,
     * banni, désactivé... et sa date d'expiration (`exp_date`, en secondes epoch).
     *
     * Fonctionne aussi bien pour une playlist enregistrée en mode Xtream que
     * pour un simple lien M3U qui se trouve être un lien Xtream déguisé
     * (voir SavedPlaylist.extractXtreamCredentials) - c'est justement ce qui
     * permet de détecter l'expiration d'un "code M3U" alors qu'aucune API
     * classique ne l'annoncerait autrement (le fichier M3U continue souvent
     * d'être servi tel quel même après expiration, seuls les flux eux-mêmes
     * cessent de fonctionner).
     *
     * Best effort : renvoie null si les identifiants n'ont pas pu être extraits,
     * en cas d'erreur réseau, ou si le panel ne renvoie pas les champs attendus -
     * dans ce cas on ne peut simplement pas se prononcer sur l'expiration, mais
     * on n'affiche jamais un message d'expiration à tort.
     */
    suspend fun checkAccountStatus(playlist: SavedPlaylist): AccountStatus? {
        val (server, user, pass) = playlist.extractXtreamCredentials() ?: return null

        return withContext(Dispatchers.IO) {
            try {
                val url = "$server/player_api.php?username=$user&password=$pass"
                val request = Request.Builder().url(url).get().build()
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use null
                    val body = response.body?.string().orEmpty()
                    val userInfo = JSONObject(body).optJSONObject("user_info") ?: return@use null

                    val statusLabel = userInfo.optString("status").takeIf { it.isNotBlank() }
                    val expDateRaw = userInfo.optString("exp_date").takeIf { it.isNotBlank() && it != "null" }
                    val expiresAtMillis = expDateRaw?.toLongOrNull()?.times(1000L)

                    val now = System.currentTimeMillis()
                    val expiredByDate = expiresAtMillis != null && expiresAtMillis < now
                    // Certains panels renvoient un status explicite ("Expired", "Banned",
                    // "Disabled") indépendamment de exp_date : on considère expiré/bloqué
                    // dès que ce n'est pas "Active", en plus de la date elle-même.
                    val expiredByStatus = statusLabel != null && !statusLabel.equals("Active", ignoreCase = true)

                    AccountStatus(
                        expired = expiredByDate || expiredByStatus,
                        statusLabel = statusLabel,
                        expiresAtMillis = expiresAtMillis
                    )
                }
            } catch (e: Exception) {
                Log.w(TAG, "Échec vérification statut abonnement : ${e.message}")
                null
            }
        }
    }
}
