package com.solplay.iptv

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.solplay.iptv.databinding.ActivityAboutBinding

class AboutActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val binding = ActivityAboutBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val licensed = TrialManager.isLicensed(this)
        binding.tvLicenseStatus.text = if (licensed) {
            "Statut : Version Pro activée ✅"
        } else {
            "Statut : Essai gratuit (${TrialManager.getRemainingTrialDays(this)} jour(s) restant(s))"
        }

        val deviceKey = DeviceKeyManager.getDeviceKey(this)
        binding.tvDeviceKeyAbout.text = deviceKey

        binding.btnCopyDeviceKeyAbout.setOnClickListener {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            clipboard.setPrimaryClip(ClipData.newPlainText("Clé appareil SolPlay", deviceKey))
            Toast.makeText(this, "Clé copiée !", Toast.LENGTH_SHORT).show()
        }
    }
}
