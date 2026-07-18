package com.solplay.desktop.ui

import android.content.Context
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.solplay.iptv.BuildConfig
import com.solplay.iptv.DeviceKeyManager
import com.solplay.iptv.TrialManager

/**
 * Équivalent desktop de l'écran/dialogue "À propos" d'Android : identifiant
 * de l'appareil et temps restant avant expiration (essai ou licence).
 * Absent jusqu'ici côté desktop - l'utilisateur ne pouvait pas savoir
 * combien de temps il lui restait sans repasser par l'écran d'activation.
 */
@Composable
fun AboutDialog(context: Context, onDismiss: () -> Unit) {
    val deviceKey = remember { DeviceKeyManager.getDeviceKey(context) }

    val remainingText = remember {
        val remainingLicense = TrialManager.getRemainingLicenseMillis(context)
        val remainingTrial = TrialManager.getRemainingTrialMillis(context)
        when {
            remainingLicense == Long.MAX_VALUE -> "Licence active (sans date d'expiration)"
            remainingLicense > 0 -> "Licence active - il reste ${TrialManager.formatDuration(remainingLicense)}"
            remainingTrial > 0 -> "Période d'essai - il reste ${TrialManager.formatDuration(remainingTrial)}"
            else -> "Aucune licence active"
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("À propos de SolPlay") },
        text = {
            Column {
                Text("Version ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(12.dp))
                Text(remainingText, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(12.dp))
                Text("Identifiant de l'appareil :", style = MaterialTheme.typography.labelMedium)
                Text(deviceKey, style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Fermer") }
        }
    )
}
