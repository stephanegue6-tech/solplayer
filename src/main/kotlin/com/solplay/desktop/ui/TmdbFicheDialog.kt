package com.solplay.desktop.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.draw.clip
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.solplay.desktop.core.AsyncImage
import com.solplay.iptv.Channel
import com.solplay.iptv.ContentType
import com.solplay.iptv.TmdbClient

/**
 * "Fiche" TMDB d'un film ou d'une série : affiche/synopsis/année, avec un
 * bouton pour lancer la lecture directement depuis la fiche. N'existe pas
 * tel quel côté Android (qui se contente d'une affiche en vignette dans la
 * liste, voir ChannelAdapter.loadTmdbFallback) - ajouté spécifiquement pour
 * desktop où l'espace écran s'y prête mieux, à la demande explicite d'une
 * "fiche TMDB".
 *
 * Recherche TMDB par titre nettoyé (TmdbClient.searchMovie/searchTv) : best
 * effort, comme sur Android - si TMDB ne renvoie rien (titre trop différent,
 * clé API absente...), la fiche s'affiche quand même avec juste le titre et
 * un bouton "Lire", sans bloquer l'utilisateur.
 */
@Composable
fun TmdbFicheDialog(
    channel: Channel,
    contentType: ContentType,
    onDismiss: () -> Unit,
    onPlay: () -> Unit
) {
    var overview by remember(channel.streamUrl) { mutableStateOf<String?>(null) }
    var year by remember(channel.streamUrl) { mutableStateOf<String?>(null) }
    var posterUrl by remember(channel.streamUrl) { mutableStateOf<String?>(channel.logoUrl) }
    var loading by remember(channel.streamUrl) { mutableStateOf(true) }

    LaunchedEffect(channel.streamUrl) {
        val result = if (contentType == ContentType.SERIES) {
            TmdbClient.searchTv(channel.name)
        } else {
            TmdbClient.searchMovie(channel.name)
        }
        result.info?.let { info ->
            overview = info.overview
            year = info.year
            if (!info.posterUrl.isNullOrBlank()) posterUrl = info.posterUrl
        }
        loading = false
    }

    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = RoundedCornerShape(12.dp), tonalElevation = 4.dp) {
            Row(Modifier.widthIn(max = 640.dp).padding(20.dp)) {
                Box(
                    Modifier.width(180.dp).height(260.dp)
                        .clip(RoundedCornerShape(8.dp))
                ) {
                    AsyncImage(posterUrl, channel.name, Modifier.fillMaxSize())
                }
                Spacer(Modifier.width(20.dp))
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                    Text(channel.name, style = MaterialTheme.typography.headlineSmall)
                    year?.let {
                        Spacer(Modifier.height(4.dp))
                        Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.outline)
                    }
                    channel.groupTitle?.let {
                        Spacer(Modifier.height(2.dp))
                        Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.outline)
                    }
                    Spacer(Modifier.height(16.dp))

                    when {
                        loading -> Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                            Text("Recherche des informations…", style = MaterialTheme.typography.bodySmall)
                        }
                        !overview.isNullOrBlank() -> Text(overview!!, style = MaterialTheme.typography.bodyMedium)
                        else -> Text(
                            "Aucun synopsis trouvé pour ce titre.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.outline
                        )
                    }

                    Spacer(Modifier.height(20.dp))
                    Row {
                        Button(onClick = onPlay) {
                            Icon(Icons.Filled.PlayArrow, contentDescription = null)
                            Spacer(Modifier.width(6.dp))
                            Text("Lire")
                        }
                        Spacer(Modifier.width(12.dp))
                        TextButton(onClick = onDismiss) { Text("Fermer") }
                    }
                }
            }
        }
    }
}
