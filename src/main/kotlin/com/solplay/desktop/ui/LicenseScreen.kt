package com.solplay.desktop.ui

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.solplay.iptv.DeviceKeyManager
import com.solplay.iptv.TrialManager
import kotlinx.coroutines.delay

/**
 * Équivalent desktop de LicenseActivity.kt : affiche la clé de cet appareil
 * (pour que l'admin l'assigne/l'active depuis son panneau), puis vérifie
 * automatiquement toutes les 10 secondes si elle a été activée - exactement
 * le même comportement que côté Android, aucune action requise de
 * l'utilisateur au-delà de communiquer sa clé.
 */
@Composable
fun LicenseScreen(context: Context, onLicensed: () -> Unit) {
    val deviceKey = remember { DeviceKeyManager.getDeviceKey(context) }
    var checking by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var remainingTrialText by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        while (true) {
            checking = true
            val active = TrialManager.checkOnlineLicense(context)
            checking = false
            if (active) {
                onLicensed()
                return@LaunchedEffect
            }
            val remainingMs = TrialManager.getRemainingTrialMillis(context)
            remainingTrialText = if (remainingMs > 0) {
                val hours = remainingMs / 3_600_000
                val minutes = (remainingMs % 3_600_000) / 60_000
                "Essai gratuit restant : ${hours}h ${minutes}min"
            } else {
                "Essai gratuit terminé"
            }
            delay(10_000)
        }
    }

    Box(Modifier.fillMaxSize().padding(48.dp), contentAlignment = Alignment.Center) {
        Card(modifier = Modifier.widthIn(max = 520.dp)) {
            Column(Modifier.padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Activation SolPlay", style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.height(16.dp))
                Text("Communiquez cette clé à votre revendeur pour activer cet ordinateur :")
                Spacer(Modifier.height(8.dp))
                SelectionContainer {
                    Text(deviceKey, style = MaterialTheme.typography.titleLarge)
                }
                Spacer(Modifier.height(16.dp))
                if (remainingTrialText.isNotEmpty()) {
                    Text(remainingTrialText, style = MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.height(8.dp))
                }
                if (checking) {
                    CircularProgressIndicator(modifier = Modifier.size(24.dp))
                } else {
                    Text(
                        "Vérification automatique toutes les 10 secondes — cet écran passera seul à l'application dès l'activation.",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                statusMessage?.let {
                    Spacer(Modifier.height(12.dp))
                    Text(it, color = MaterialTheme.colorScheme.error)
                }
                Spacer(Modifier.height(20.dp))
                Button(onClick = {
                    if (TrialManager.getRemainingTrialMillis(context) > 0) onLicensed()
                    else statusMessage = "Essai terminé. Merci de contacter votre revendeur avec votre clé ci-dessus."
                }) {
                    Text("Continuer avec l'essai gratuit")
                }
            }
        }
    }
}
