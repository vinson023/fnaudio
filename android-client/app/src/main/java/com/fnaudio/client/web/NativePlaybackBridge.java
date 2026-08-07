package com.fnaudio.client.web;

import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;

import androidx.annotation.Nullable;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.Player;
import androidx.media3.session.MediaController;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public final class NativePlaybackBridge {
    public interface ControllerProvider {
        @Nullable
        MediaController controller();
    }

    public interface HttpRequestHandler {
        void requestJson(String requestId, String method, String url, String headersJson, String body);
    }

    private final ControllerProvider provider;
    private final HttpRequestHandler httpRequestHandler;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public NativePlaybackBridge(ControllerProvider provider, HttpRequestHandler httpRequestHandler) {
        this.provider = provider;
        this.httpRequestHandler = httpRequestHandler;
    }

    @JavascriptInterface
    public boolean isAvailable() {
        return true;
    }

    @JavascriptInterface
    public void requestJson(String requestId, String method, String url, String headersJson, String body) {
        if (requestId == null || requestId.trim().isEmpty()) return;
        httpRequestHandler.requestJson(
                requestId.trim(),
                method == null ? "GET" : method,
                url == null ? "" : url,
                headersJson == null ? "{}" : headersJson,
                body == null ? "" : body
        );
    }

    @JavascriptInterface
    public void setQueue(String json, int currentIndex, double positionSeconds, boolean autoPlay, String repeat, boolean shuffle) {
        final List<MediaItem> items;
        try {
            items = parseItems(new JSONArray(json));
        } catch (Exception exception) {
            return;
        }
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller == null || items.isEmpty()) return;
            int safeIndex = Math.max(0, Math.min(currentIndex, items.size() - 1));
            long positionMs = Math.max(0L, Math.round(positionSeconds * 1000d));
            controller.setMediaItems(items, safeIndex, positionMs);
            controller.setRepeatMode(repeatMode(repeat));
            controller.setShuffleModeEnabled(shuffle);
            controller.prepare();
            if (autoPlay) controller.play();
        });
    }

    @JavascriptInterface
    public void play() {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller == null) return;
            if (controller.getPlaybackState() == Player.STATE_IDLE) controller.prepare();
            controller.play();
        });
    }

    @JavascriptInterface
    public void pause() {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller != null) controller.pause();
        });
    }

    @JavascriptInterface
    public void stop() {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller != null) controller.stop();
        });
    }

    @JavascriptInterface
    public void next() {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller != null && controller.hasNextMediaItem()) controller.seekToNextMediaItem();
        });
    }

    @JavascriptInterface
    public void previous() {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller != null && controller.hasPreviousMediaItem()) controller.seekToPreviousMediaItem();
        });
    }

    @JavascriptInterface
    public void seekTo(double seconds) {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller != null) controller.seekTo(Math.max(0L, Math.round(seconds * 1000d)));
        });
    }

    @JavascriptInterface
    public void setVolume(double value) {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller != null) controller.setVolume((float) Math.max(0d, Math.min(1d, value)));
        });
    }

    @JavascriptInterface
    public void setRepeat(String repeat) {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller != null) controller.setRepeatMode(repeatMode(repeat));
        });
    }

    @JavascriptInterface
    public void setShuffle(boolean enabled) {
        mainHandler.post(() -> {
            MediaController controller = provider.controller();
            if (controller != null) controller.setShuffleModeEnabled(enabled);
        });
    }

    private static List<MediaItem> parseItems(JSONArray array) {
        List<MediaItem> items = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject row = array.optJSONObject(i);
            if (row == null) continue;
            String id = row.optString("id");
            String uri = row.optString("uri");
            if (id.isEmpty() || uri.isEmpty()) continue;
            MediaMetadata.Builder metadata = new MediaMetadata.Builder()
                    .setTitle(row.optString("title", "fnAudio"))
                    .setArtist(row.optString("artist"))
                    .setAlbumTitle(row.optString("album"));
            long durationMs = row.optLong("durationMs", 0L);
            if (durationMs > 0) metadata.setDurationMs(durationMs);
            String artwork = row.optString("artwork");
            if (!artwork.isEmpty()) metadata.setArtworkUri(Uri.parse(artwork));
            items.add(new MediaItem.Builder()
                    .setMediaId(id)
                    .setUri(Uri.parse(uri))
                    .setMediaMetadata(metadata.build())
                    .build());
        }
        return items;
    }

    private static int repeatMode(String repeat) {
        if ("one".equalsIgnoreCase(repeat)) return Player.REPEAT_MODE_ONE;
        if ("all".equalsIgnoreCase(repeat)) return Player.REPEAT_MODE_ALL;
        return Player.REPEAT_MODE_OFF;
    }
}
