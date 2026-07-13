package com.solplay.iptv

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.solplay.iptv.databinding.ActivityChannelsBinding

class ChannelsActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_CHANNELS = "extra_channels"
    }

    private lateinit var binding: ActivityChannelsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityChannelsBinding.inflate(layoutInflater)
        setContentView(binding.root)

       val channels = channelRepository.channels

        binding.recyclerChannels.layoutManager = LinearLayoutManager(this)
        binding.recyclerChannels.adapter = ChannelAdapter(channels) { channel ->
            val intent = Intent(this, PlayerActivity::class.java)
            intent.putExtra(PlayerActivity.EXTRA_STREAM_URL, channel.streamUrl)
            intent.putExtra(PlayerActivity.EXTRA_STREAM_NAME, channel.name)
            startActivity(intent)
        }
    }
}
