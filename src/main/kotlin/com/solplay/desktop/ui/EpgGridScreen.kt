package com.solplay.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.focusTarget
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.solplay.iptv.Channel
import com.solplay.iptv.EpgGridUtils
import com.solplay.iptv.SavedPlaylist
import com.solplay.iptv.XtreamApiClient
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

private const val WINDOW_HOURS = 3
private const val SLOT_MINUTES = 30
private const val SLOT_WIDTH_DP = 110
private const val ROW_HEIGHT_DP = 56
private const val HEADER_HEIGHT_DP = 32
private const val NAME_COLUMN_WIDTH_DP = 180

/**
 * Grille EPG multi-chaînes façon "zappeur", équivalent desktop de
 * EpgGridActivity côté Android. Toutes les chaînes sont affichées sur une
 * frise horaire commune.
 *
 * Différence volontaire avec l'implémentation Android (RecyclerView +
 * défilement synchronisé manuellement via SyncHorizontalScrollView) : ici,
 * l'en-tête des heures ET toutes les lignes de chaînes partagent un seul et
 * même ScrollState horizontal (et un seul ScrollState vertical pour la
 * colonne des noms de chaînes) - Compose garde alors tout aligné
 * automatiquement, sans code de synchronisation manuel à maintenir.
 */
@Composable
fun EpgGridScreen(
    channels: List<Channel>,
    playlist: SavedPlaylist,
    onBack: () -> Unit
) {
    val calendar = remember { Calendar.getInstance() }
    val windowStart = remember {
        val minute = calendar.get(Calendar.MINUTE)
        calendar.set(Calendar.MINUTE, if (minute < 30) 0 else 30)
        calendar.set(Calendar.SECOND, 0)
        calendar.set(Calendar.MILLISECOND, 0)
        calendar.timeInMillis
    }
    val windowEnd = remember { windowStart + WINDOW_HOURS * 60 * 60 * 1000L }
    val slotCount = remember { ((windowEnd - windowStart) / (SLOT_MINUTES * 60 * 1000L)).toInt() }
    val pxPerMinute = SLOT_WIDTH_DP.toFloat() / SLOT_MINUTES

    val hScroll = rememberScrollState()
    val vScroll = rememberScrollState()
    val sdf = remember { SimpleDateFormat("HH:mm", Locale.getDefault()) }
    val scope = rememberCoroutineScope()
    val gridFocusRequester = remember { FocusRequester() }
    val density = androidx.compose.ui.platform.LocalDensity.current
    val rowHeightPx = with(density) { ROW_HEIGHT_DP.dp.toPx() }
    val slotWidthPx = with(density) { SLOT_WIDTH_DP.dp.toPx() }

    LaunchedEffect(Unit) { gridFocusRequester.requestFocus() }

    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, contentDescription = "Retour") }
            Spacer(Modifier.width(8.dp))
            Text("Guide des programmes", style = MaterialTheme.typography.titleMedium)
        }
        Divider()

        if (channels.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Aucune chaîne Live à afficher.", color = MaterialTheme.colorScheme.outline)
            }
            return@Column
        }

        Row(Modifier.weight(1f)) {
            // Colonne fixe des noms de chaînes : partage le scroll vertical
            // avec la zone de droite pour rester alignée ligne par ligne.
            Column(
                Modifier.width(NAME_COLUMN_WIDTH_DP.dp).verticalScroll(vScroll)
            ) {
                Spacer(Modifier.height(HEADER_HEIGHT_DP.dp))
                channels.forEach { channel ->
                    Box(
                        Modifier.fillMaxWidth().height(ROW_HEIGHT_DP.dp).padding(horizontal = 8.dp),
                        contentAlignment = Alignment.CenterStart
                    ) {
                        Text(
                            channel.name,
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            }

            // Zone de droite : en-tête horaire + lignes de programmes, dans
            // UN SEUL conteneur qui défile à la fois horizontalement (frise
            // temporelle) et verticalement (synchronisé avec la colonne des
            // noms via le même vScroll).
            Column(
                Modifier.weight(1f)
                    .horizontalScroll(hScroll)
                    .verticalScroll(vScroll)
                    .focusRequester(gridFocusRequester)
                    .focusTarget()
                    .onPreviewKeyEvent { event ->
                        if (event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                        when (event.key) {
                            Key.DirectionDown -> {
                                scope.launch { vScroll.animateScrollTo((vScroll.value + rowHeightPx).toInt()) }
                                true
                            }
                            Key.DirectionUp -> {
                                scope.launch { vScroll.animateScrollTo((vScroll.value - rowHeightPx).toInt()) }
                                true
                            }
                            Key.DirectionRight -> {
                                scope.launch { hScroll.animateScrollTo((hScroll.value + slotWidthPx).toInt()) }
                                true
                            }
                            Key.DirectionLeft -> {
                                scope.launch { hScroll.animateScrollTo((hScroll.value - slotWidthPx).toInt()) }
                                true
                            }
                            else -> false
                        }
                    }
            ) {
                Row(Modifier.height(HEADER_HEIGHT_DP.dp)) {
                    repeat(slotCount) { i ->
                        val t = windowStart + i * SLOT_MINUTES * 60 * 1000L
                        Box(
                            Modifier.width(SLOT_WIDTH_DP.dp).fillMaxHeight(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(sdf.format(Date(t)), style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
                Divider()

                channels.forEach { channel ->
                    EpgChannelRow(channel, playlist, windowStart, windowEnd, pxPerMinute)
                }
            }
        }
    }
}

@Composable
private fun EpgChannelRow(
    channel: Channel,
    playlist: SavedPlaylist,
    windowStart: Long,
    windowEnd: Long,
    pxPerMinute: Float
) {
    var segments by remember(channel.streamUrl) { mutableStateOf<List<EpgGridUtils.Segment>?>(null) }

    LaunchedEffect(channel.streamUrl) {
        val streamId = XtreamApiClient.extractStreamId(channel.streamUrl)
        if (streamId <= 0) {
            segments = emptyList()
            return@LaunchedEffect
        }
        val raw = XtreamApiClient.fetchProgramSlotsRaw(playlist, streamId)
        segments = EpgGridUtils.buildSegments(raw, windowStart, windowEnd)
    }

    Row(Modifier.height(ROW_HEIGHT_DP.dp)) {
        val current = segments
        if (current == null) {
            Box(
                Modifier.width(SLOT_WIDTH_DP.dp * ((windowEnd - windowStart) / (SLOT_MINUTES * 60 * 1000L)).toInt())
                    .fillMaxHeight(),
                contentAlignment = Alignment.CenterStart
            ) {
                Text(
                    "Chargement…",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.padding(start = 8.dp)
                )
            }
        } else {
            current.forEach { segment ->
                val widthDp = ((segment.endMillis - segment.startMillis) / 60000f) * pxPerMinute
                Box(
                    Modifier.width(widthDp.dp).fillMaxHeight()
                        .padding(horizontal = 1.dp, vertical = 2.dp)
                        .background(
                            if (segment.isPlaceholder) MaterialTheme.colorScheme.surfaceVariant
                            else MaterialTheme.colorScheme.primaryContainer
                        )
                        .padding(6.dp),
                    contentAlignment = Alignment.CenterStart
                ) {
                    Text(
                        segment.title,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = if (segment.isPlaceholder) FontWeight.Normal else FontWeight.Medium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        color = if (segment.isPlaceholder) MaterialTheme.colorScheme.outline
                                else MaterialTheme.colorScheme.onPrimaryContainer
                    )
                }
            }
        }
    }
}
