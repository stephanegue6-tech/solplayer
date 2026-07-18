package com.solplay.iptv

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Vérifie sur GitHub Releases si une version plus récente de l'application
 * est disponible que celle actuellement installée.
 *
 * Ne dépend d'aucun format de tag particulier : on regarde uniquement le nom
 * du fichier ".msi"/".exe" attaché à la dernière release (ex. "SolPlay-1.2.0.msi")
 * et on en extrait le numéro de version pour le comparer à currentVersionName.
 */
object UpdateChecker {

    private const val TAG = "UpdateChecker"

    // Dépôt GitHub où sont publiées les releases contenant l'installeur Windows.
    private const val GITHUB_OWNER = "stephanegue6-tech"
    private const val GITHUB_REPO = "solplay-VII"

    private const val API_URL =
        "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/releases/latest"

    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(4, TimeUnit.SECONDS)
        .build()

    data class UpdateInfo(
        val versionName: String,
        val downloadUrl: String
    )

    /**
     * Retourne un UpdateInfo si une version plus récente que [currentVersionName]
     * est disponible, sinon null (y compris en cas d'erreur réseau : on ne
     * bloque jamais le démarrage de l'app pour ça).
     */
    suspend fun checkForUpdate(currentVersionName: String): UpdateInfo? = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url(API_URL)
                // Obligatoire : l'API GitHub refuse les requêtes sans User-Agent.
                .header("User-Agent", "SolPlay-UpdateChecker")
                .header("Accept", "application/vnd.github+json")
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(TAG, "Réponse GitHub non OK: ${response.code}")
                    return@withContext null
                }

                val body = response.body?.string() ?: return@withContext null
                val json = JSONObject(body)
                val assets = json.optJSONArray("assets") ?: return@withContext null

                // Priorité au .msi (installeur standard Windows) puis .exe
                // en repli, en ignorant les .apk (releases Android partagées
                // dans le même dépôt/même page de release).
                var installerName: String? = null
                var installerUrl: String? = null
                for (ext in listOf(".msi", ".exe")) {
                    for (i in 0 until assets.length()) {
                        val asset = assets.getJSONObject(i)
                        val name = asset.optString("name")
                        if (name.endsWith(ext, ignoreCase = true)) {
                            installerName = name
                            installerUrl = asset.optString("browser_download_url")
                            break
                        }
                    }
                    if (installerName != null) break
                }

                if (installerName == null || installerUrl.isNullOrEmpty()) {
                    Log.w(TAG, "Aucun installeur Windows (.msi/.exe) trouvé dans la dernière release")
                    return@withContext null
                }

                val remoteVersion = extractVersion(installerName)
                if (remoteVersion == null) {
                    Log.w(TAG, "Impossible d'extraire un numéro de version de: $installerName")
                    return@withContext null
                }

                return@withContext if (isNewer(remoteVersion, currentVersionName)) {
                    UpdateInfo(versionName = remoteVersion, downloadUrl = installerUrl)
                } else {
                    null
                }
            }
        } catch (e: Exception) {
            // Pas de réseau, timeout, JSON invalide, etc. -> on ignore simplement.
            Log.w(TAG, "Vérification de mise à jour impossible: ${e.message}")
            null
        }
    }

    /**
     * Extrait un numéro de version type "1.2" ou "1.2.3" d'un nom de fichier
     * comme "SolPlay-1.2.msi" ou "SolPlay-1.2.3.exe".
     */
    private fun extractVersion(fileName: String): String? {
        val regex = Regex("""(\d+(?:\.\d+)+)""")
        return regex.find(fileName)?.value
    }

    /**
     * Compare deux versions au format "X.Y.Z" (nombre de segments variable).
     * Retourne true si [remote] est strictement plus récent que [local].
     */
    private fun isNewer(remote: String, local: String): Boolean {
        val remoteParts = remote.split(".").mapNotNull { it.toIntOrNull() }
        val localParts = local.split(".").mapNotNull { it.toIntOrNull() }

        val maxLength = maxOf(remoteParts.size, localParts.size)
        for (i in 0 until maxLength) {
            val r = remoteParts.getOrElse(i) { 0 }
            val l = localParts.getOrElse(i) { 0 }
            if (r != l) return r > l
        }
        return false
    }
}
