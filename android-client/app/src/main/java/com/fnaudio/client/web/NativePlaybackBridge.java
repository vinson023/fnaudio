package com.fnaudio.client.web;

import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.net.Uri;
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
import java.util.UUID;

public final class NativePlaybackBridge {
    private static final int MAX_QUEUE_JSON_BYTES = 512 * 1024;
    private static final int MAX_HTTP_BODY_BYTES = 512 * 1024;
    private static final int MAX_HTTP_HEADERS_BYTES = 64 * 1024;
    private static final int MAX_HTTP_URL_BYTES = 8192;
    private static final int MAX_REQUEST_ID_LENGTH = 256;
    private static final int MAX_TARGET_ID_LENGTH = 256;
    private static final int MAX_TARGET_NAME_LENGTH = 512;
    private static final int MAX_MEDIA_ID_LENGTH = 256;
    private static final int MAX_MEDIA_TEXT_LENGTH = 512;
    private static final int MAX_QUEUE_ITEMS = 500;
    private static final long MAX_TIME_MS = 7L * 24L * 60L * 60L * 1000L;
    private static final long MAX_FALLBACK_ARTWORK_BYTES = 128L * 1024L;
    private static final Object FALLBACK_ARTWORK_LOCK = new Object();
    public interface ControllerCommand {
        void run(MediaController controller);
    }

    public interface ControllerProvider {
        @Nullable
        MediaController controller();

        void dispatchWhenReady(ControllerCommand command);
    }

    public interface HttpRequestHandler {
        void requestJson(String requestId, String method, String url, String headersJson, String body);

        void cancelRequestJson(String requestId);

        void rejectRequestJson(String requestId, String message);
    }

    private final ControllerProvider provider;
    private final HttpRequestHandler httpRequestHandler;
    private final Context context;
    @Nullable
    private final Uri fallbackArtworkUri;

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
        enterRemoteMode(targetId, targetName, queueJson, currentIndex, positionSeconds, durationSeconds,
                playing, repeat, shuffle, System.currentTimeMillis() & 0x7fffffffL, 1L);
    }

    @JavascriptInterface
    public void enterRemoteMode(String targetId, String targetName, String queueJson, int currentIndex,
                                 double positionSeconds, double durationSeconds, boolean playing,
                                 String repeat, boolean shuffle, long generation, long engineEpoch) {
        if (boundedText(targetId, MAX_TARGET_ID_LENGTH).isEmpty()
                || !boundedUtf8(queueJson, MAX_QUEUE_JSON_BYTES)) return;
        Intent intent = new Intent(context, PlaybackService.class)
                .setAction(PlaybackService.ACTION_REMOTE_ENABLE)
                .putExtra(PlaybackService.EXTRA_TARGET_ID, boundedText(targetId, MAX_TARGET_ID_LENGTH))
                .putExtra(PlaybackService.EXTRA_TARGET_NAME, boundedText(targetName, MAX_TARGET_NAME_LENGTH))
                .putExtra(PlaybackService.EXTRA_QUEUE_JSON, queueJson == null ? "[]" : queueJson)
                .putExtra(PlaybackService.EXTRA_INDEX, currentIndex)
                .putExtra(PlaybackService.EXTRA_POSITION_MS, safeTimeMs(positionSeconds))
                .putExtra(PlaybackService.EXTRA_DURATION_MS, safeTimeMs(durationSeconds))
                .putExtra(PlaybackService.EXTRA_PLAYING, playing)
                .putExtra(PlaybackService.EXTRA_REPEAT_MODE, repeatMode(repeat))
                .putExtra(PlaybackService.EXTRA_SHUFFLE, shuffle);
        intent.putExtra(PlaybackService.EXTRA_SESSION_GENERATION, Math.max(0L, generation))
                .putExtra(PlaybackService.EXTRA_ENGINE_EPOCH, Math.max(0L, engineEpoch));
        startPlaybackService(intent, true);
    }

    @JavascriptInterface
    public void updateRemoteState(String targetId, int currentIndex, double positionSeconds,
                                  double durationSeconds, boolean playing) {
        updateRemoteState(targetId, currentIndex, positionSeconds, durationSeconds, playing, -1L, -1L);
    }

    /**
     * Applies a remote snapshot only to the session identity that produced it.
     * The legacy overload remains for older WebViews, while current pages pass
     * generation and engine epoch to prevent delayed bridge callbacks from
     * crossing a target/process boundary.
     */
    @JavascriptInterface
    public void updateRemoteState(String targetId, int currentIndex, double positionSeconds,
                                  double durationSeconds, boolean playing, long generation,
                                  long engineEpoch) {
        Intent intent = new Intent(context, PlaybackService.class)
                .setAction(PlaybackService.ACTION_REMOTE_UPDATE)
                .putExtra(PlaybackService.EXTRA_TARGET_ID, boundedText(targetId, MAX_TARGET_ID_LENGTH))
                .putExtra(PlaybackService.EXTRA_INDEX, currentIndex)
                .putExtra(PlaybackService.EXTRA_POSITION_MS, safeTimeMs(positionSeconds))
                .putExtra(PlaybackService.EXTRA_DURATION_MS, safeTimeMs(durationSeconds))
                .putExtra(PlaybackService.EXTRA_PLAYING, playing);
        if (generation >= 0L) {
            intent.putExtra(PlaybackService.EXTRA_SESSION_GENERATION, Math.max(0L, generation));
        }
        if (engineEpoch >= 0L) {
            intent.putExtra(PlaybackService.EXTRA_ENGINE_EPOCH, Math.max(0L, engineEpoch));
        }
        startPlaybackService(intent, true);
    }

    @JavascriptInterface
    public void exitRemoteMode() {
        startPlaybackService(new Intent(context, PlaybackService.class).setAction(PlaybackService.ACTION_LOCAL_ENABLE), false);
    }

    @JavascriptInterface
    public void requestJson(String requestId, String method, String url, String headersJson, String body) {
        String safeRequestId = requestId == null ? "" : requestId.trim();
        if (safeRequestId.isEmpty() || safeRequestId.length() > MAX_REQUEST_ID_LENGTH) return;
        if (httpRequestHandler == null) return;
        if (!boundedUtf8(url, MAX_HTTP_URL_BYTES)
                || !boundedUtf8(headersJson, MAX_HTTP_HEADERS_BYTES)
                || !boundedUtf8(body, MAX_HTTP_BODY_BYTES)) {
            // Complete the WebView request immediately instead of leaving its
            // promise pending until the long bridge timeout.
            httpRequestHandler.rejectRequestJson(safeRequestId, "原生网络请求输入过大");
            return;
        }
        httpRequestHandler.requestJson(
                safeRequestId,
                method == null ? "GET" : method,
                url == null ? "" : url,
                headersJson == null ? "{}" : headersJson,
                body == null ? "" : body
        );
    }

    @JavascriptInterface
    public void cancelRequestJson(String requestId) {
        String safeRequestId = requestId == null ? "" : requestId.trim();
        if (safeRequestId.isEmpty() || safeRequestId.length() > MAX_REQUEST_ID_LENGTH) return;
        if (httpRequestHandler != null) httpRequestHandler.cancelRequestJson(safeRequestId);
    }

    @JavascriptInterface
    public void setQueue(String json, int currentIndex, double positionSeconds, boolean autoPlay, String repeat, boolean shuffle) {
        if (!boundedUtf8(json, MAX_QUEUE_JSON_BYTES)) return;
        final List<MediaItem> items;
        try {
            items = parseItems(new JSONArray(json));
        } catch (Exception exception) {
            return;
        }
        if (items.isEmpty()) return;
        int safeIndex = Math.max(0, Math.min(currentIndex, items.size() - 1));
        long positionMs = safeTimeMs(positionSeconds);
        provider.dispatchWhenReady(controller -> {
            controller.setMediaItems(items, safeIndex, positionMs);
            controller.setRepeatMode(repeatMode(repeat));
            controller.setShuffleModeEnabled(shuffle);
            controller.prepare();
            if (autoPlay) controller.play();
        });
    }

    @JavascriptInterface
    public void play() {
        provider.dispatchWhenReady(controller -> {
            if (controller.getPlaybackState() == Player.STATE_IDLE) controller.prepare();
            controller.play();
        });
    }

    @JavascriptInterface
    public void pause() {
        provider.dispatchWhenReady(MediaController::pause);
    }

    @JavascriptInterface
    public void stop() {
        provider.dispatchWhenReady(MediaController::stop);
    }

    @JavascriptInterface
    public void next() {
        provider.dispatchWhenReady(controller -> {
            if (controller.hasNextMediaItem()) controller.seekToNextMediaItem();
        });
    }

    @JavascriptInterface
    public void previous() {
        provider.dispatchWhenReady(controller -> {
            if (controller.hasPreviousMediaItem()) controller.seekToPreviousMediaItem();
        });
    }

    @JavascriptInterface
    public void seekTo(double seconds) {
        provider.dispatchWhenReady(controller -> controller.seekTo(safeTimeMs(seconds)));
    }

    @JavascriptInterface
    public void setVolume(double value) {
        float safeVolume = Double.isFinite(value) ? (float) Math.max(0d, Math.min(1d, value)) : 0f;
        provider.dispatchWhenReady(controller -> controller.setVolume(safeVolume));
    }

    @JavascriptInterface
    public void setRepeat(String repeat) {
        provider.dispatchWhenReady(controller -> controller.setRepeatMode(repeatMode(repeat)));
    }

    @JavascriptInterface
    public void setShuffle(boolean enabled) {
        provider.dispatchWhenReady(controller -> controller.setShuffleModeEnabled(enabled));
    }

    private List<MediaItem> parseItems(JSONArray array) {
        List<MediaItem> items = new ArrayList<>();
        for (int i = 0; i < Math.min(array.length(), MAX_QUEUE_ITEMS); i++) {
            JSONObject row = array.optJSONObject(i);
            if (row == null) continue;
            String id = boundedText(stringField(row, "id"), MAX_MEDIA_ID_LENGTH);
            String uri = boundedText(stringField(row, "uri"), MAX_HTTP_URL_BYTES);
            if (id.isEmpty() || uri.isEmpty() || !isHttpUri(uri)) continue;
            MediaMetadata.Builder metadata = new MediaMetadata.Builder()
                    .setTitle(boundedText(stringField(row, "title", "fnAudio"), MAX_MEDIA_TEXT_LENGTH))
                    .setArtist(boundedText(stringField(row, "artist"), MAX_MEDIA_TEXT_LENGTH))
                    .setAlbumTitle(boundedText(stringField(row, "album"), MAX_MEDIA_TEXT_LENGTH));
            long durationMs = longField(row, "durationMs");
            if (durationMs > 0) metadata.setDurationMs(Math.min(MAX_TIME_MS, durationMs));
            String artwork = boundedText(stringField(row, "artwork"), MAX_HTTP_URL_BYTES);
            if (!artwork.isEmpty() && isHttpUri(artwork)) metadata.setArtworkUri(Uri.parse(artwork));
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
    private static String stringField(JSONObject row, String key) {
        return stringField(row, key, "");
    }

    private static String stringField(JSONObject row, String key, String fallback) {
        Object value = row == null ? null : row.opt(key);
        return value instanceof String ? (String) value : fallback;
    }

    private static long longField(JSONObject row, String key) {
        Object value = row == null ? null : row.opt(key);
        if (value instanceof Boolean || !(value instanceof Number)) return 0L;
        double numeric = ((Number) value).doubleValue();
        if (!Double.isFinite(numeric) || numeric < 0d || numeric != Math.rint(numeric)
                || numeric > Long.MAX_VALUE) return 0L;
        return ((Number) value).longValue();
    }

    private static boolean isHttpUri(String value) {
        try {
            Uri uri = Uri.parse(value);
            String scheme = uri.getScheme();
            return uri.getHost() != null
                    && uri.getUserInfo() == null
                    && (uri.getPort() == -1 || (uri.getPort() >= 1 && uri.getPort() <= 65535))
                    && ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme));
        } catch (RuntimeException ignored) {
            return false;
        }
    }

    @Nullable
    private static Uri createFallbackArtworkUri(Context context) {
        File file = new File(context.getFilesDir(), "media_placeholder_white.png");
        synchronized (FALLBACK_ARTWORK_LOCK) {
            if (!isUsableFallbackArtwork(file)) {
                Bitmap bitmap = null;
                File temporary = new File(file.getPath() + ".tmp." + UUID.randomUUID());
                try {
                    bitmap = Bitmap.createBitmap(512, 512, Bitmap.Config.ARGB_8888);
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

                    try (FileOutputStream output = new FileOutputStream(temporary)) {
                        if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
                                || !temporary.renameTo(file)) return null;
                    }
                } catch (OutOfMemoryError | IOException | RuntimeException ignored) {
                    return null;
                } finally {
                    if (bitmap != null) bitmap.recycle();
                    //noinspection ResultOfMethodCallIgnored
                    temporary.delete();
                }
            }
        }
        return Uri.fromFile(file);
    }

    private static boolean isUsableFallbackArtwork(File file) {
        if (!file.isFile() || file.length() <= 0L || file.length() > MAX_FALLBACK_ARTWORK_BYTES) {
            return false;
        }
        try {
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inJustDecodeBounds = true;
            BitmapFactory.decodeFile(file.getPath(), options);
            return options.outWidth == 512 && options.outHeight == 512;
        } catch (OutOfMemoryError | RuntimeException ignored) {
            return false;
        }
    }

    private static int repeatMode(String repeat) {
        if ("one".equalsIgnoreCase(repeat)) return Player.REPEAT_MODE_ONE;
        if ("all".equalsIgnoreCase(repeat)) return Player.REPEAT_MODE_ALL;
        return Player.REPEAT_MODE_OFF;
    }

    private static String boundedText(String value, int maxLength) {
        if (value == null || maxLength < 0 || value.length() > maxLength) return "";
        String trimmed = value.trim();
        return trimmed.length() <= maxLength ? trimmed : "";
    }

    private static boolean boundedUtf8(String value, int maxBytes) {
        if (value == null) return true;
        if (maxBytes < 0 || value.length() > maxBytes) return false;
        int bytes = 0;
        for (int index = 0; index < value.length(); index++) {
            char valueAtIndex = value.charAt(index);
            if (valueAtIndex <= 0x7f) {
                bytes += 1;
            } else if (valueAtIndex <= 0x7ff) {
                bytes += 2;
            } else if (Character.isHighSurrogate(valueAtIndex)
                    && index + 1 < value.length()
                    && Character.isLowSurrogate(value.charAt(index + 1))) {
                bytes += 4;
                index += 1;
            } else if (Character.isSurrogate(valueAtIndex)) {
                // String.getBytes(UTF_8) encodes an unpaired surrogate as the
                // three-byte UTF-8 replacement character.
                bytes += 3;
            } else {
                bytes += 3;
            }
            if (bytes > maxBytes) return false;
        }
        return true;
    }

    private static long safeTimeMs(double seconds) {
        if (!Double.isFinite(seconds) || seconds <= 0d) return 0L;
        return Math.min(MAX_TIME_MS, Math.round(seconds * 1000d));
    }

    private void startPlaybackService(Intent intent, boolean foreground) {
        // A remote output has no local decoder. It still needs a MediaSession
        // immediately, including while the renderer is paused, connecting, or
        // awaiting its first authoritative SSE snapshot.
        if (foreground) ContextCompat.startForegroundService(context, intent);
        else context.startService(intent);
    }
}
