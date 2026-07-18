package com.solplay.desktop.ui

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.solplay.iptv.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private enum class Mode { CODE, M3U, XTREAM }

/**
 * Équivalent desktop de PlaylistsListActivity + PlaylistActivity : permet
 * de se connecter via un code fourni par l'admin, un lien M3U, ou des
 * identifiants Xtream - et se synchronise/connecte automatiquement si
 * l'admin a assigné un compte à la clé de cet appareil (même logique que
 * SplashActivity côté Android : voir DevicePlaylistSync.sync()).
 */
@Composable
fun ConnectScreen(context: Context, onConnected: (SavedPlaylist) -> Unit) {
    val scope = rememberCoroutineScope()
    var mode by remember { mutableStateOf(Mode.CODE) }
    var code by remember { mutableStateOf("") }
    var m3uUrl by remember { mutableStateOf("") }
    var xtreamServer by remember { mutableStateOf("") }
    var xtreamUser by remember { mutableStateOf("") }
    var xtreamPass by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var autoSyncMessage by remember { mutableStateOf<String?>(null) }

    // Au premier affichage : comme SplashActivity côté Android, vérifie si
    // l'admin a déjà assigné/activé un compte pour cette clé appareil, et
    // s'y connecte automatiquement sans que l'utilisateur ait besoin de
    // saisir quoi que ce soit.
    LaunchedEffect(Unit) {
        autoSyncMessage = "Vérification d'un compte assigné par votre revendeur…"
        DevicePlaylistSync.sync(context)
        val assigned = PlaylistStore.getAll(context).firstOrNull { it.fromCode?.startsWith("device:") == true }
        if (assigned != null) {
            autoSyncMessage = "Compte trouvé, connexion en cours…"
            connectAndLoad(context, assigned, onConnected) { msg -> error = msg }
        } else {
            autoSyncMessage = null
        }
    }

    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.TopCenter) {
        Card(Modifier.widthIn(max = 560.dp).verticalScroll(rememberScrollState())) {
            Column(Modifier.padding(28.dp)) {
                Text("Connexion à votre abonnement", style = MaterialTheme.typography.headlineSmall)
                Spacer(Modifier.height(4.dp))
                autoSyncMessage?.let {
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                        Text(it, style = MaterialTheme.typography.bodySmall)
                    }
                }
                Spacer(Modifier.height(20.dp))

                TabRow(selectedTabIndex = mode.ordinal) {
                    Tab(selected = mode == Mode.CODE, onClick = { mode = Mode.CODE }, text = { Text("Code") })
                    Tab(selected = mode == Mode.M3U, onClick = { mode = Mode.M3U }, text = { Text("Lien M3U") })
                    Tab(selected = mode == Mode.XTREAM, onClick = { mode = Mode.XTREAM }, text = { Text("Xtream") })
                }
                Spacer(Modifier.height(20.dp))

                when (mode) {
                    Mode.CODE -> {
                        OutlinedTextField(code, { code = it }, label = { Text("Code fourni par votre revendeur") }, modifier = Modifier.fillMaxWidth())
                    }
                    Mode.M3U -> {
                        OutlinedTextField(m3uUrl, { m3uUrl = it }, label = { Text("URL de la playlist M3U") }, modifier = Modifier.fillMaxWidth())
                    }
                    Mode.XTREAM -> {
                        OutlinedTextField(xtreamServer, { xtreamServer = it }, label = { Text("Serveur (http://exemple.com:8080)") }, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(xtreamUser, { xtreamUser = it }, label = { Text("Utilisateur") }, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(xtreamPass, { xtreamPass = it }, label = { Text("Mot de passe") }, modifier = Modifier.fillMaxWidth())
                    }
                }

                error?.let {
                    Spacer(Modifier.height(12.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }

                Spacer(Modifier.height(20.dp))
                Button(
                    enabled = !loading,
                    onClick = {
                        error = null
                        loading = true
                        scope.launch {
                            val playlist: SavedPlaylist? = when (mode) {
                                Mode.CODE -> when (val r = CodeRedeemer.redeem(code)) {
                                    is RedeemResult.Success -> r.playlist
                                    is RedeemResult.Failure -> { error = r.message; null }
                                }
                                Mode.M3U -> if (m3uUrl.isBlank()) { error = "Merci de saisir un lien."; null }
                                    else SavedPlaylist(name = "Ma playlist", mode = PlaylistMode.M3U, m3uUrl = m3uUrl.trim())
                                Mode.XTREAM -> if (xtreamServer.isBlank() || xtreamUser.isBlank() || xtreamPass.isBlank()) {
                                    error = "Merci de remplir les 3 champs."; null
                                } else SavedPlaylist(
                                    name = "Ma playlist",
                                    mode = PlaylistMode.XTREAM,
                                    xtreamServer = xtreamServer.trim(),
                                    xtreamUsername = xtreamUser.trim(),
                                    xtreamPassword = xtreamPass.trim()
                                )
                            }
                            if (playlist != null) {
                                connectAndLoad(context, playlist, onConnected) { msg -> error = msg }
                            }
                            loading = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    if (loading) CircularProgressIndicator(Modifier.size(18.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                    else Text("Se connecter")
                }
            }
        }
    }
}

private suspend fun connectAndLoad(
    context: Context,
    playlist: SavedPlaylist,
    onConnected: (SavedPlaylist) -> Unit,
    onError: (String) -> Unit
) {
    try {
        val channels = withContext(Dispatchers.IO) {
            if (playlist.extractXtreamCredentials() != null) {
                XtreamApiClient.fetchAllChannelsDirect(playlist).channels
            } else {
                val parsed = M3uParser.fetchAndParse(playlist.buildUrl())
                XtreamApiClient.enrichChannelsWithCategories(playlist, parsed)
            }
        }
        if (channels.isEmpty()) {
            onError("Aucune chaîne trouvée pour cette playlist.")
            return
        }
        PlaylistStore.save(context, playlist)
        PlaylistStore.setActiveId(context, playlist.id)
        ChannelCacheStore.save(context, playlist.id, channels)
        ChannelRepository.setChannels(channels)
        onConnected(playlist)
    } catch (e: PlaylistLoadException) {
        onError(e.message ?: "Erreur de chargement.")
    } catch (e: Exception) {
        onError("Erreur de connexion : ${e.message ?: "inconnue"}.")
    }
}
