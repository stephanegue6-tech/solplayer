package com.solplay.iptv

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.solplay.iptv.databinding.ActivityRedeemCodeBinding
import kotlinx.coroutines.launch

class RedeemCodeActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRedeemCodeBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRedeemCodeBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnValidateCode.setOnClickListener {
            val code = binding.etCode.text.toString()
            binding.progressBarCode.visibility = android.view.View.VISIBLE
            binding.btnValidateCode.isEnabled = false
            lifecycleScope.launch {
                when (val result = CodeRedeemer.redeem(code)) {
                    is RedeemResult.Success -> {
                        PlaylistStore.save(this@RedeemCodeActivity, result.playlist)
                        Toast.makeText(
                            this@RedeemCodeActivity,
                            "Playlist « ${result.playlist.name} » ajoutée !",
                            Toast.LENGTH_LONG
                        ).show()
                        finish()
                    }
                    is RedeemResult.Failure -> {
                        binding.progressBarCode.visibility = android.view.View.GONE
                        binding.btnValidateCode.isEnabled = true
                        Toast.makeText(this@RedeemCodeActivity, result.message, Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }
}
