package com.solplay.desktop.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * Palette reprise de l'app Android (voir colors.xml : solplay_orange,
 * solplay_black, solplay_white, solplay_gray). Sans ce thème, Compose
 * Desktop utilisait le schéma Material3 par défaut (violet), complètement
 * déconnecté de l'identité visuelle de l'app - d'où la différence de
 * couleurs remarquée entre les deux versions.
 */
object SolPlayColors {
    val Orange = Color(0xFFFF7A00)
    val OrangeDark = Color(0xFFCC6200)
    val Green = Color(0xFF2ECC71)
    val Black = Color(0xFF111318)
    val SurfaceDark = Color(0xFF1C1F26)
    val Gray = Color(0xFF2A2E37)
    val White = Color(0xFFFFFFFF)

    // Panneau "Changer de chaîne" en surimpression sur la vidéo (écran de
    // lecture) : mêmes couleurs ARGB que colors.xml côté Android
    // (solplay_panel_overlay, solplay_panel_header_overlay,
    // solplay_search_bg_overlay, solplay_white_60), pour un rendu identique
    // - fond sombre semi-transparent (pas blanc opaque) qui laisse deviner
    // la vidéo derrière, comme sur mobile.
    val PanelOverlay = Color(0xCC1A1A1A)
    val PanelHeaderOverlay = Color(0xD9E56A00)
    val SearchOverlayBg = Color(0x33FFFFFF)
    val White60 = Color(0x99FFFFFF)
}

private val SolPlayDarkScheme = darkColorScheme(
    primary = SolPlayColors.Orange,
    onPrimary = SolPlayColors.Black,
    primaryContainer = SolPlayColors.OrangeDark,
    onPrimaryContainer = SolPlayColors.White,
    secondary = SolPlayColors.Orange,
    background = SolPlayColors.Black,
    onBackground = SolPlayColors.White,
    surface = SolPlayColors.SurfaceDark,
    onSurface = SolPlayColors.White,
    surfaceVariant = SolPlayColors.Gray,
    onSurfaceVariant = SolPlayColors.White,
    outline = Color(0xFF9AA0AA)
)

/**
 * Enveloppe l'app entière avec la palette SolPlay. isSystemInDarkTheme()
 * n'a pas vraiment de sens hors Android/mobile ici : l'app Android est déjà
 * pensée en thème sombre par défaut (fonds noirs dans les layouts), donc on
 * applique directement ce même thème sombre sans varier selon le système.
 */
@Composable
fun SolPlayTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = SolPlayDarkScheme,
        content = content
    )
}
