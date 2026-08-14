package com.fnaudio.client.web;

import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;

import androidx.annotation.Nullable;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.Player;
import androidx.media3.session.MediaController;
import androidx.core.content.ContextCompat;

import com.fnaudio.client.playback.PlaybackService;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
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
    private final Context context;
    @Nullable
    private final Uri fallbackArtworkUri;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public NativePlaybackBridge(Context context, ControllerProvider provider, HttpRequestHandler httpRequestHandler) {
        this.context = context.getApplicationContext();
        this.fallbackArtworkUri = createFallbackArtworkUri(context.getApplicationContext());
        this.provider = provider;
        this.httpRequestHandler = httpRequestHandler;
    }

    @JavascriptInterface
    public boolean isAvailable() {
        return true;
    }

    /** Switches the native MediaSession to a metadata/control-only remote player. */
    @JavascriptInterface
    public void enterRemoteMode(String targetId, String targetName, String queueJson, int currentIndex,
                                 double positionSeconds, double durationSeconds, boolean playing,
                                 String repeat, boolean shuffle) {
        Intent intent = new Intent(context, PlaybackService.class)
                .setAction(PlaybackService.ACTION_REMOTE_ENABLE)
                .putExtra(PlaybackService.EXTRA_TARGET_ID, targetId == null ? "" : targetId)
                .putExtra(PlaybackService.EXTRA_TARGET_NAME, targetName == null ? "" : targetName)
                .putExtra(PlaybackService.EXTRA_QUEUE_JSON, queueJson == null ? "[]" : queueJson)
                .putExtra(PlaybackService.EXTRA_INDEX, currentIndex)
                .putExtra(PlaybackService.EXTRA_POSITION_MS, Math.max(0L, Math.round(positionSeconds * 1000d)))
                .putExtra(PlaybackService.EXTRA_DURATION_MS, Math.max(0L, Math.round(durationSeconds * 1000d)))
                .putExtra(PlaybackService.EXTRA_PLAYING, playing)
                .putExtra(PlaybackService.EXTRA_REPEAT_MODE, repeatMode(repeat))
                .putExtra(PlaybackService.EXTRA_SHUFFLE, shuffle);
        startPlaybackService(intent, true);
    }

    @JavascriptInterface
    public void updateRemoteState(String targetId, int currentIndex, double positionSeconds,
                                  double durationSeconds, boolean playing) {
        Intent intent = new Intent(context, PlaybackService.class)
                .setAction(PlaybackService.ACTION_REMOTE_UPDATE)
                .putExtra(PlaybackService.EXTRA_TARGET_ID, targetId == null ? "" : targetId)
                .putExtra(PlaybackService.EXTRA_INDEX, currentIndex)
                .putExtra(PlaybackService.EXTRA_POSITION_MS, Math.max(0L, Math.round(positionSeconds * 1000d)))
                .putExtra(PlaybackService.EXTRA_DURATION_MS, Math.max(0L, Math.round(durationSeconds * 1000d)))
                .putExtra(PlaybackService.EXTRA_PLAYING, playing);
        startPlaybackService(intent, true);
    }

    @JavascriptInterface
    public void exitRemoteMode() {
        startPlaybackService(new Intent(context, PlaybackService.class).setAction(PlaybackService.ACTION_LOCAL_ENABLE), false);
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

    private List<MediaItem> parseItems(JSONArray array) {
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
            else if (fallbackArtworkUri != null) metadata.setArtworkUri(fallbackArtworkUri);
            items.add(new MediaItem.Builder()
                    .setMediaId(id)
                    .setUri(Uri.parse(uri))
                    .setMediaMetadata(metadata.build())
                    .build());
        }
        return items;
    }

    @Nullable
    private static Uri createFallbackArtworkUri(Context context) {
        File file = new File(context.getFilesDir(), "media_placeholder_white.png");
        if (!file.exists() || file.length() == 0L) {
            Bitmap bitmap = Bitmap.createBitmap(512, 512, Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(bitmap);
            Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
            paint.setColor(Color.WHITE);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(34f);
            canvas.drawCircle(256f, 256f, 170f, paint);

            Path triangle = new Path();
            triangle.moveTo(224f, 170f);
            triangle.lineTo(224f, 342f);
            triangle.lineTo(354f, 256f);
            triangle.close();
            paint.setStyle(Paint.Style.FILL);
            canvas.drawPath(triangle, paint);

            try (FileOutputStream output = new FileOutputStream(file)) {
                if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) return null;
            } catch (IOException ignored) {
                return null;
            } finally {
                bitmap.recycle();
            }
        }
        return Uri.fromFile(file);
    }

    private static int repeatMode(String repeat) {
        if ("one".equalsIgnoreCase(repeat)) return Player.REPEAT_MODE_ONE;
        if ("all".equalsIgnoreCase(repeat)) return Player.REPEAT_MODE_ALL;
        return Player.REPEAT_MODE_OFF;
    }

    private void startPlaybackService(Intent intent, boolean foreground) {
        // A remote output has no local decoder. It still needs a MediaSession
        // immediately, including while the renderer is paused, connecting, or
        // awaiting its first authoritative SSE snapshot.
        if (foreground) ContextCompat.startForegroundService(context, intent);
        else context.startService(intent);
    }
}
