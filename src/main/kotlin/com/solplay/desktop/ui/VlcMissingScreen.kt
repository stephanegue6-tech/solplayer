package com.solplay.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.solplay.desktop.core.VlcCheck
import com.solplay.desktop.core.openUrlInBrowser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Affiché à la place de l'écran suivant normalement prévu (Connexion ou
 * Licence) quand VLC Media Player n'est pas détectable sur la machine -
 * bloquant volontairement, car aucune fonctionnalité de lecture ne peut
 * marcher sans VLC (voir VlcCheck.kt et PlayerScreen.kt).
 */
@Composable
fun VlcMissingScreen(onVlcFound: () -> Unit) {
    var checking by remember { mutableStateOf(false) }
    var stillMissing by remember { mutableStateOf(false) }
    var browserOpenFailed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun retry() {
        checking = true
        stillMissing = false
        scope.launch {
            val found = withContext(Dispatchers.IO) { VlcCheck.isAvailable() }
            checking = false
            if (found) onVlcFound() else stillMissing = true
        }
    }

    Box(Modifier.fillMaxSize().background(SolPlayColors.Black), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.widthIn(max = 480.dp).padding(24.dp)
        ) {
            Text("VLC Media Player requis", color = SolPlayColors.White, fontSize = 24.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(12.dp))
            Text(
                "SolPlay utilise VLC pour lire les chaînes, films et séries. " +
                    "Il n'a pas été détecté sur cet ordinateur. C'est gratuit et l'installation prend 2 minutes.",
                color = SolPlayColors.White.copy(alpha = 0.75f),
                textAlign = TextAlign.Center
            )
            Spacer(Modifier.height(24.dp))

            Button(onClick = {
                if (!openUrlInBrowser(VlcCheck.DOWNLOAD_URL)) browserOpenFailed = true
            }) {
                Text("Télécharger VLC")
            }

            if (browserOpenFailed) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "Impossible d'ouvrir le navigateur automatiquement. Copiez ce lien :\n${VlcCheck.DOWNLOAD_URL}",
                    color = SolPlayColors.White.copy(alpha = 0.75f),
                    textAlign = TextAlign.Center,
                    fontSize = 12.sp
                )
            }

            Spacer(Modifier.height(16.dp))

            OutlinedButton(onClick = { retry() }, enabled = !checking) {
                Text(if (checking) "Vérification…" else "J'ai installé VLC, réessayer")
            }

            if (stillMissing) {
                Spacer(Modifier.height(12.dp))
                Text(
                    "VLC n'a toujours pas été détecté. Vérifiez que l'installation est bien terminée, " +
                        "puis réessayez. Un redémarrage de SolPlay peut aussi être nécessaire.",
                    color = MaterialTheme.colorScheme.error,
                    textAlign = TextAlign.Center,
                    fontSize = 13.sp
                )
            }
        }
    }
}
