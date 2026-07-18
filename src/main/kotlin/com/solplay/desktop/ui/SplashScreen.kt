package com.solplay.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.solplay.desktop.core.VlcCheck
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay

/**
 * [onDone] reçoit si VLC a été détecté sur la machine, vérifié en parallèle
 * du petit délai d'affichage du splash (donc sans coût de temps perçu dans
 * le cas courant où VLC est déjà installé) - voir VlcCheck.kt.
 */
@Composable
fun SplashScreen(onDone: (vlcAvailable: Boolean) -> Unit) {
    LaunchedEffect(Unit) {
        val vlcCheck = async(Dispatchers.IO) { VlcCheck.isAvailable() }
        delay(1200)
        onDone(vlcCheck.await())
    }
    Box(Modifier.fillMaxSize().background(SolPlayColors.Black), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("SolPlay", color = SolPlayColors.Orange, fontSize = 42.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Text("Votre lecteur IPTV nouvelle génération", color = SolPlayColors.White.copy(alpha = 0.7f), fontSize = 14.sp)
            Spacer(Modifier.height(20.dp))
            Box(Modifier.width(60.dp).height(4.dp).background(SolPlayColors.Green))
        }
    }
}
