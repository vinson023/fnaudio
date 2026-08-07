package com.fnaudio.client.playback;

import android.content.Intent;

import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.Player;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.datasource.okhttp.OkHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.session.DefaultMediaNotificationProvider;
import androidx.media3.session.MediaSession;
import androidx.media3.session.MediaSessionService;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.HttpClientFactory;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

@OptIn(markerClass = UnstableApi.class)
public final class PlaybackService extends MediaSessionService {
    private ExoPlayer player;
    private MediaSession mediaSession;

    @Override
    public void onCreate() {
        super.onCreate();
        DefaultMediaNotificationProvider notificationProvider = new DefaultMediaNotificationProvider(this);
        notificationProvider.setSmallIcon(R.drawable.ic_notification);
        setMediaNotificationProvider(notificationProvider);

        ConnectionProfile profile = PlaybackRuntimeConfig.activeProfile();
        if (profile == null) profile = new SecureProfileStore(this).active();

        okhttp3.OkHttpClient httpClient = HttpClientFactory.create(profile);
        OkHttpDataSource.Factory dataSourceFactory = new OkHttpDataSource.Factory(httpClient)
                .setUserAgent("fnAudio-Android");
        if (profile != null && !profile.token.isEmpty()) {
            String encodedToken = encodeCookie(profile.token);
            Map<String, String> headers = new LinkedHashMap<>();
            headers.put("Authorization", "Bearer " + profile.token);
            headers.put("X-Fnaudio-Trim-Token", profile.token);
            headers.put("Cookie", "fnaudio_trim_token=" + encodedToken + "; trim_token=" + encodedToken + "; token=" + encodedToken);
            dataSourceFactory.setDefaultRequestProperties(headers);
        }

        player = new ExoPlayer.Builder(this)
                .setMediaSourceFactory(new DefaultMediaSourceFactory(dataSourceFactory))
                .build();
        player.setAudioAttributes(AudioAttributes.DEFAULT, true);
        player.setHandleAudioBecomingNoisy(true);
        player.setWakeMode(C.WAKE_MODE_LOCAL);
        mediaSession = new MediaSession.Builder(this, player).build();
    }

    @Nullable
    @Override
    public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return mediaSession;
    }

    @Override
    public void onTaskRemoved(@Nullable Intent rootIntent) {
        if (player == null || !player.getPlayWhenReady() || player.getPlaybackState() == Player.STATE_ENDED) {
            stopSelf();
        }
    }

    @Override
    public void onDestroy() {
        if (mediaSession != null) {
            mediaSession.release();
            mediaSession = null;
        }
        if (player != null) {
            player.release();
            player = null;
        }
        super.onDestroy();
    }

    private static String encodeCookie(String value) {
        try {
            return URLEncoder.encode(value, "UTF-8");
        } catch (Exception ignored) {
            return value;
        }
    }
}
