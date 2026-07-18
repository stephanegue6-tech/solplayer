package com.solplay.desktop.core

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.toComposeImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.jetbrains.skia.Image as SkiaImage
import java.net.URI
import java.util.concurrent.ConcurrentHashMap

/**
 * Équivalent minimal de Coil (utilisé côté Android via ImageLoader.kt, une
 * librairie Android-only indisponible sur JVM desktop) : charge une image
 * depuis une URL en tâche de fond et l'affiche, avec un cache mémoire pour
 * éviter de retélécharger la même affiche/logo à chaque recomposition
 * (scroll, changement d'onglet...).
 *
 * Utilisé pour les logos de chaînes et les affiches TMDB (voir
 * TmdbFicheDialog et HomeScreen).
 */
private object ImageCache {
    val cache = ConcurrentHashMap<String, ImageBitmap>()
}

private suspend fun fetchImageBitmap(url: String): ImageBitmap? {
    ImageCache.cache[url]?.let { return it }
    return withContext(Dispatchers.IO) {
        try {
            // Comme pour M3uParser.kt : de nombreux CDN de logos IPTV
            // renvoient une erreur (403/vide) face au User-Agent par défaut
            // de Java ("Java/17...") et exigent un User-Agent de navigateur.
            // C'était la cause des logos qui échouaient TOUS systématiquement,
            // pas juste certains.
            val connection = URI(url).toURL().openConnection() as java.net.HttpURLConnection
            connection.connectTimeout = 10000
            connection.readTimeout = 15000
            connection.instanceFollowRedirects = true
            connection.setRequestProperty(
                "User-Agent",
                "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
            )

            val bytes = connection.inputStream.use { it.readBytes() }
            val bitmap = SkiaImage.makeFromEncoded(bytes).toComposeImageBitmap()
            ImageCache.cache[url] = bitmap
            bitmap
        } catch (e: Exception) {
            null
        }
    }
}

@Composable
fun AsyncImage(
    url: String?,
    contentDescription: String?,
    modifier: Modifier = Modifier,
    // Fit par défaut (image entière visible, avec un léger espace vide sur
    // les côtés si le ratio ne correspond pas) plutôt que Crop (remplit
    // tout le cadre en coupant ce qui dépasse) : pour une affiche de film
    // (portrait), Crop coupait le haut et le bas de l'image - inacceptable
    // pour une affiche, contrairement à un logo carré où ça passerait
    // inaperçu. Un appelant peut toujours repasser en Crop explicitement
    // s'il veut vraiment remplir un cadre carré sans bande vide.
    contentScale: ContentScale = ContentScale.Fit
) {
    // IMPORTANT : url est nullable (beaucoup de films/séries n'ont pas de
    // logoUrl dans le M3U) - ConcurrentHashMap interdit les clés null et
    // plante immédiatement dessus ("Cannot invoke Object.hashCode() because
    // <parameter1> is null") si on ne filtre pas avant d'aller lire le cache.
    var bitmap by remember(url) { mutableStateOf(url?.let { ImageCache.cache[it] }) }
    var failed by remember(url) { mutableStateOf(false) }

    LaunchedEffect(url) {
        if (url.isNullOrBlank()) {
            failed = true
            return@LaunchedEffect
        }
        val result = fetchImageBitmap(url)
        if (result != null) bitmap = result else failed = true
    }

    Box(modifier, contentAlignment = Alignment.Center) {
        val b = bitmap
        when {
            b != null -> Image(
                bitmap = b,
                contentDescription = contentDescription,
                modifier = Modifier.fillMaxSize(),
                contentScale = contentScale
            )
            failed -> Icon(
                Icons.Filled.Warning,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.outline
            )
            else -> CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
        }
    }
}
