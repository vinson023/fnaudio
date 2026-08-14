package com.fnaudio.client.playback;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
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
import com.fnaudio.client.ui.MainActivity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Locale;
import java.util.UUID;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

@OptIn(markerClass = UnstableApi.class)
public final class PlaybackService extends MediaSessionService {
    public static final String ACTION_REMOTE_ENABLE = "com.fnaudio.client.playback.REMOTE_ENABLE";
    public static final String ACTION_REMOTE_UPDATE = "com.fnaudio.client.playback.REMOTE_UPDATE";
    public static final String ACTION_LOCAL_ENABLE = "com.fnaudio.client.playback.LOCAL_ENABLE";
    public static final String EXTRA_TARGET_ID = "target_id";
    public static final String EXTRA_TARGET_NAME = "target_name";
    public static final String EXTRA_QUEUE_JSON = "queue_json";
    public static final String EXTRA_INDEX = "index";
    public static final String EXTRA_POSITION_MS = "position_ms";
    public static final String EXTRA_DURATION_MS = "duration_ms";
    public static final String EXTRA_PLAYING = "playing";
    public static final String EXTRA_REPEAT_MODE = "repeat_mode";
    public static final String EXTRA_SHUFFLE = "shuffle";

    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    // The WebView receives server-sent state while it is active. Native
    // polling is only a background/suspended-WebView recovery path.
    private static final long REMOTE_POLL_INTERVAL_MS = 5000L;
    private static final long REMOTE_BRIDGE_GRACE_MS = 4500L;
    private static final long REMOTE_EVENT_RETRY_MS = 1000L;
    private static final String REMOTE_NOTIFICATION_CHANNEL = "fnaudio_remote_playback";
    private static final int REMOTE_NOTIFICATION_ID = 7011;

    private ExoPlayer player;
    private RemotePlaybackPlayer remotePlayer;
    private MediaSession mediaSession;
    private AuthenticatedBitmapLoader bitmapLoader;
    private ConnectionProfile profile;
    private OkHttpClient httpClient;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private String remoteTargetId = "";
    private String remoteTargetName = "";
    private boolean remotePollInFlight;
    private volatile long remoteBridgeUpdateAt;
    @Nullable private volatile Call remoteEventCall;
    private volatile boolean remoteEventConnected;
    private final Runnable remotePoll = this::pollRemoteStatus;
    private final Runnable remoteEventRetry = this::startRemoteEventStream;

    @Override
    public void onCreate() {
        super.onCreate();
        // Keep one Media3-owned notification for both local and remote output.
        // A plain foreground notification is not a media notification, so it is
        // not reliably surfaced by Android on the lock screen or in media
        // controls when the phone is only mirroring a DAC/DLNA output.
        DefaultMediaNotificationProvider notificationProvider = new DefaultMediaNotificationProvider.Builder(this)
                .setNotificationId(REMOTE_NOTIFICATION_ID)
                .setChannelId(REMOTE_NOTIFICATION_CHANNEL)
                .build();
        notificationProvider.setSmallIcon(R.drawable.ic_notification);
        setMediaNotificationProvider(notificationProvider);
        setShowNotificationForIdlePlayer(SHOW_NOTIFICATION_FOR_IDLE_PLAYER_ALWAYS);

        profile = PlaybackRuntimeConfig.activeProfile();
        if (profile == null) profile = new SecureProfileStore(this).active();

        httpClient = HttpClientFactory.create(this, profile);
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
        remotePlayer = new RemotePlaybackPlayer(Looper.getMainLooper(), this::sendRemoteCommand);
        bitmapLoader = new AuthenticatedBitmapLoader(this, profile, httpClient);
        mediaSession = new MediaSession.Builder(this, player)
                .setBitmapLoader(bitmapLoader)
                .build();
    }

    @Override
    public int onStartCommand(@Nullable Intent intent, int flags, int startId) {
        if (intent != null) {
            String action = intent.getAction();
            if (ACTION_REMOTE_ENABLE.equals(action)) enableRemoteMode(intent);
            else if (ACTION_REMOTE_UPDATE.equals(action)) updateRemoteMode(intent);
            else if (ACTION_LOCAL_ENABLE.equals(action)) enableLocalMode();
        }
        return super.onStartCommand(intent, flags, startId);
    }

    @Nullable
    @Override
    public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return mediaSession;
    }

    @Override
    public void onUpdateNotification(MediaSession session, boolean startInForegroundRequired) {
        if (session == mediaSession && remotePlayer != null && remotePlayer.isRemoteActive()) {
            publishRemoteMediaNotification();
            return;
        }
        super.onUpdateNotification(session, startInForegroundRequired);
    }

    @Override
    public void onTaskRemoved(@Nullable Intent rootIntent) {
        if (remotePlayer != null && remotePlayer.isRemoteActive()) return;
        if (player == null || !player.getPlayWhenReady() || player.getPlaybackState() == Player.STATE_ENDED) {
            stopSelf();
        }
    }

    @Override
    public void onDestroy() {
        mainHandler.removeCallbacks(remotePoll);
        mainHandler.removeCallbacks(remoteEventRetry);
        closeRemoteEventStream();
        if (mediaSession != null) {
            mediaSession.release();
            mediaSession = null;
        }
        if (bitmapLoader != null) {
            bitmapLoader.shutdown();
            bitmapLoader = null;
        }
        if (player != null) {
            player.release();
            player = null;
        }
        if (remotePlayer != null) {
            remotePlayer.release();
            remotePlayer = null;
        }
        super.onDestroy();
    }

    private void enableRemoteMode(Intent intent) {
        if (mediaSession == null || remotePlayer == null || player == null) return;
        String targetId = clean(intent.getStringExtra(EXTRA_TARGET_ID));
        if (targetId.isEmpty() || "local".equals(targetId)) return;
        List<MediaItem> items = parseRemoteItems(intent.getStringExtra(EXTRA_QUEUE_JSON));
        if (items.isEmpty()) return;
        remoteTargetId = targetId;
        remoteTargetName = clean(intent.getStringExtra(EXTRA_TARGET_NAME));
        player.pause();
        player.stop();
        remotePlayer.activate(
                items,
                intent.getIntExtra(EXTRA_INDEX, 0),
                intent.getLongExtra(EXTRA_POSITION_MS, 0L),
                intent.getLongExtra(EXTRA_DURATION_MS, 0L),
                intent.getBooleanExtra(EXTRA_PLAYING, false),
                intent.getIntExtra(EXTRA_REPEAT_MODE, Player.REPEAT_MODE_OFF),
                intent.getBooleanExtra(EXTRA_SHUFFLE, false)
        );
        if (mediaSession.getPlayer() != remotePlayer) mediaSession.setPlayer(remotePlayer);
        ensureRemoteForeground();
        remoteBridgeUpdateAt = SystemClock.elapsedRealtime();
        startRemoteEventStream();
        scheduleRemotePoll(REMOTE_BRIDGE_GRACE_MS + 250L);
    }

    private void updateRemoteMode(Intent intent) {
        if (remotePlayer == null || !remotePlayer.isRemoteActive()) return;
        String targetId = clean(intent.getStringExtra(EXTRA_TARGET_ID));
        if (!targetId.isEmpty() && !targetId.equals(remoteTargetId)) return;
        if (remoteEventConnected) return;
        remotePlayer.updateStatus(
                intent.getIntExtra(EXTRA_INDEX, remotePlayer.getCurrentMediaItemIndex()),
                intent.getLongExtra(EXTRA_POSITION_MS, Math.max(0L, remotePlayer.getCurrentPosition())),
                intent.getLongExtra(EXTRA_DURATION_MS, Math.max(0L, remotePlayer.getDuration())),
                intent.getBooleanExtra(EXTRA_PLAYING, remotePlayer.isRemotePlaying())
        );
        remoteBridgeUpdateAt = SystemClock.elapsedRealtime();
        ensureRemoteForeground();
    }

    private void enableLocalMode() {
        mainHandler.removeCallbacks(remotePoll);
        remoteTargetId = "";
        remoteTargetName = "";
        remotePollInFlight = false;
        remoteBridgeUpdateAt = 0L;
        closeRemoteEventStream();
        if (remotePlayer != null) remotePlayer.deactivate();
        if (mediaSession != null && player != null && mediaSession.getPlayer() != player) mediaSession.setPlayer(player);
        stopForeground(true);
    }

    private void ensureRemoteForeground() {
        if (mediaSession == null || remotePlayer == null || !remotePlayer.isRemoteActive()) return;
        publishRemoteMediaNotification();
    }

    private void publishRemoteMediaNotification() {
        if (mediaSession == null || remotePlayer == null || !remotePlayer.isRemoteActive()) return;
        // MediaSessionService does not elevate a paused remote-only player by
        // itself. Start immediately with a platform MediaStyle notification
        // carrying the real session token. Remote updates use this same path
        // so Media3 cannot discard it merely because no local decoder exists.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    REMOTE_NOTIFICATION_CHANNEL,
                    "fnAudio playback",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Remote playback controls");
            channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
        MediaItem current = remotePlayer.currentRemoteItem();
        MediaMetadata metadata = current == null ? MediaMetadata.EMPTY : current.mediaMetadata;
        String title = metadata.title == null ? "fnAudio" : metadata.title.toString();
        String artist = metadata.artist == null ? remoteTargetName : metadata.artist.toString();
        Intent openApp = new Intent(this, MainActivity.class)
                .setAction(MainActivity.ACTION_OPEN_PLAYBACK)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this,
                0,
                openApp,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, REMOTE_NOTIFICATION_CHANNEL)
                : new Notification.Builder(this);
        Notification notification = builder
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(artist == null || artist.isEmpty() ? remoteTargetName : artist)
                .setContentIntent(contentIntent)
                .setCategory(Notification.CATEGORY_TRANSPORT)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setStyle(new Notification.MediaStyle().setMediaSession(mediaSession.getPlatformToken()))
                .build();
        startForeground(REMOTE_NOTIFICATION_ID, notification);
    }

    private void sendRemoteCommand(String action, @Nullable Long positionMs) {
        if (remoteTargetId.isEmpty() || profile == null || httpClient == null) return;
        JSONObject payload = new JSONObject();
        try {
            payload.put("target_id", remoteTargetId);
            payload.put("action", action);
            payload.put("command_id", "android-" + UUID.randomUUID());
            if (positionMs != null) payload.put("position", Math.max(0L, positionMs) / 1000d);
            MediaItem current = remotePlayer == null ? null : remotePlayer.currentRemoteItem();
            if (current != null) payload.put("track_id", current.mediaId);
            if ("repeat".equals(action) && remotePlayer != null) {
                payload.put("repeat", repeatName(remotePlayer.getRemoteRepeatMode()));
            } else if ("shuffle".equals(action) && remotePlayer != null) {
                payload.put("shuffle", remotePlayer.isRemoteShuffleEnabled());
            }
        } catch (Exception ignored) {
            return;
        }
        Request request = authenticatedRequest(profile.fnAudioUrl() + "api/playback/control")
                .post(RequestBody.create(payload.toString(), JSON))
                .build();
        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException exception) {
                scheduleRemotePoll(300L);
            }

            @Override
            public void onResponse(Call call, Response response) {
                try (Response ignored = response) {
                    if (response.body() != null) {
                        JSONObject data = new JSONObject(response.body().string());
                        applyRemoteCore(data.optJSONObject("core"));
                    }
                } catch (Exception ignored) {
                }
                // Notification actions can arrive while WebView is suspended.
                // Force one authoritative refresh after their command result.
                remoteBridgeUpdateAt = 0L;
                scheduleRemotePoll(150L);
            }
        });
    }

    private void pollRemoteStatus() {
        mainHandler.removeCallbacks(remotePoll);
        if (remotePlayer == null || !remotePlayer.isRemoteActive() || remoteTargetId.isEmpty()
                || profile == null || httpClient == null || remotePollInFlight) return;
        if (remoteEventConnected) return;
        long sinceBridge = SystemClock.elapsedRealtime() - remoteBridgeUpdateAt;
        if (remoteBridgeUpdateAt > 0L && sinceBridge < REMOTE_BRIDGE_GRACE_MS) {
            scheduleRemotePoll(REMOTE_BRIDGE_GRACE_MS - sinceBridge + 100L);
            return;
        }
        remotePollInFlight = true;
        String url = profile.fnAudioUrl() + "api/playback/status?target_id=" + encodeQuery(remoteTargetId);
        httpClient.newCall(authenticatedRequest(url).get().build()).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException exception) {
                remotePollInFlight = false;
                scheduleRemotePoll(REMOTE_POLL_INTERVAL_MS);
            }

            @Override
            public void onResponse(Call call, Response response) {
                try (Response ignored = response) {
                    if (response.isSuccessful() && response.body() != null) {
                        applyRemoteStatus(new JSONObject(response.body().string()));
                    }
                } catch (Exception ignored) {
                } finally {
                    remotePollInFlight = false;
                    scheduleRemotePoll(REMOTE_POLL_INTERVAL_MS);
                }
            }
        });
    }

    private void applyRemoteStatus(JSONObject data) {
        JSONObject transport = data.optJSONObject("transport");
        JSONObject position = data.optJSONObject("position");
        JSONObject core = data.optJSONObject("core");
        String state = transport == null ? "" : transport.optString("state").toUpperCase(Locale.ROOT);
        boolean playing = "PLAYING".equals(state) || "TRANSITIONING".equals(state);
        long positionMs = position == null ? 0L : Math.max(0L, Math.round(position.optDouble("rel_seconds", 0d) * 1000d));
        long durationMs = position == null ? 0L : Math.max(0L, Math.round(position.optDouble("duration_seconds", 0d) * 1000d));
        mainHandler.post(() -> {
            if (remotePlayer != null && remotePlayer.isRemoteActive()) {
                int index = indexFromCore(core);
                int safeIndex = index < 0 ? remotePlayer.getCurrentMediaItemIndex() : index;
                remotePlayer.updateStatus(safeIndex, positionMs, durationMs, playing);
            }
        });
    }

    private void applyRemoteCore(@Nullable JSONObject core) {
        mainHandler.post(() -> {
            if (remotePlayer != null && remotePlayer.isRemoteActive()) {
                int index = indexFromCore(core);
                if (index < 0) return;
                remotePlayer.updateStatus(index, 0L, Math.max(0L, remotePlayer.getDuration()), remotePlayer.isRemotePlaying());
            }
        });
    }

    private int indexFromCore(@Nullable JSONObject core) {
        if (core == null || remotePlayer == null) return -1;
        String current = core.optString("current");
        if (current.isEmpty()) return -1;
        for (int i = 0; i < remotePlayer.getMediaItemCount(); i++) {
            if (current.equals(remotePlayer.getMediaItemAt(i).mediaId)) return i;
        }
        return -1;
    }

    private void scheduleRemotePoll(long delayMs) {
        mainHandler.removeCallbacks(remotePoll);
        mainHandler.postDelayed(remotePoll, Math.max(0L, delayMs));
    }

    private void startRemoteEventStream() {
        mainHandler.removeCallbacks(remoteEventRetry);
        if (remoteTargetId.isEmpty() || profile == null || httpClient == null
                || remotePlayer == null || !remotePlayer.isRemoteActive()) return;
        closeRemoteEventStream();
        String targetId = remoteTargetId;
        String url = profile.fnAudioUrl() + "api/playback/events?target_id=" + encodeQuery(targetId);
        Call call = httpClient.newCall(authenticatedRequest(url)
                .header("Accept", "text/event-stream")
                .get()
                .build());
        remoteEventCall = call;
        call.enqueue(new Callback() {
            @Override
            public void onFailure(Call failed, IOException exception) {
                onRemoteEventStreamEnded(call);
            }

            @Override
            public void onResponse(Call activeCall, Response response) {
                try (Response ignored = response) {
                    if (!response.isSuccessful() || response.body() == null) return;
                    readRemoteEventStream(activeCall, response);
                } catch (Exception ignored) {
                } finally {
                    onRemoteEventStreamEnded(activeCall);
                }
            }
        });
    }

    private void readRemoteEventStream(Call call, Response response) throws IOException {
        StringBuilder data = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(response.body().byteStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (call != remoteEventCall) return;
                if (line.startsWith("data:")) {
                    if (data.length() > 0) data.append('\n');
                    data.append(line.substring(5).trim());
                    continue;
                }
                if (!line.isEmpty() || data.length() == 0) continue;
                try {
                    JSONObject snapshot = new JSONObject(data.toString());
                    if (!remoteTargetId.equals(snapshot.optString("target_id"))) continue;
                    remoteEventConnected = true;
                    remoteBridgeUpdateAt = SystemClock.elapsedRealtime();
                    applyRemoteStatus(snapshot);
                } catch (Exception ignored) {
                } finally {
                    data.setLength(0);
                }
            }
        }
    }

    private void onRemoteEventStreamEnded(Call call) {
        if (call != remoteEventCall) return;
        remoteEventConnected = false;
        remoteEventCall = null;
        scheduleRemotePoll(250L);
        mainHandler.postDelayed(remoteEventRetry, REMOTE_EVENT_RETRY_MS);
    }

    private void closeRemoteEventStream() {
        Call call = remoteEventCall;
        remoteEventCall = null;
        remoteEventConnected = false;
        if (call != null) call.cancel();
    }

    private Request.Builder authenticatedRequest(String url) {
        Request.Builder request = new Request.Builder().url(url);
        if (profile != null && !profile.token.isEmpty()) {
            String encodedToken = encodeCookie(profile.token);
            request.header("Authorization", "Bearer " + profile.token)
                    .header("X-Fnaudio-Trim-Token", profile.token)
                    .header("Cookie", "fnaudio_trim_token=" + encodedToken + "; trim_token=" + encodedToken + "; token=" + encodedToken);
        }
        return request;
    }

    private List<MediaItem> parseRemoteItems(@Nullable String json) {
        List<MediaItem> items = new ArrayList<>();
        Uri fallbackArtwork = Uri.fromFile(new File(getFilesDir(), "media_placeholder_white.png"));
        try {
            JSONArray array = new JSONArray(json == null ? "[]" : json);
            for (int i = 0; i < array.length(); i++) {
                JSONObject row = array.optJSONObject(i);
                if (row == null) continue;
                String id = clean(row.optString("id"));
                if (id.isEmpty()) continue;
                MediaMetadata.Builder metadata = new MediaMetadata.Builder()
                        .setTitle(row.optString("title", "fnAudio"))
                        .setArtist(row.optString("artist"))
                        .setAlbumTitle(row.optString("album"));
                long durationMs = row.optLong("durationMs", 0L);
                if (durationMs > 0L) metadata.setDurationMs(durationMs);
                String artwork = clean(row.optString("artwork"));
                metadata.setArtworkUri(artwork.isEmpty() ? fallbackArtwork : Uri.parse(artwork));
                items.add(new MediaItem.Builder()
                        .setMediaId(id)
                        .setMediaMetadata(metadata.build())
                        .build());
            }
        } catch (Exception ignored) {
            items.clear();
        }
        return items;
    }

    private static String clean(@Nullable String value) {
        return value == null ? "" : value.trim();
    }

    private static String repeatName(int mode) {
        if (mode == Player.REPEAT_MODE_ONE) return "one";
        if (mode == Player.REPEAT_MODE_ALL) return "all";
        return "off";
    }

    private static String encodeQuery(String value) {
        try {
            return URLEncoder.encode(value, StandardCharsets.UTF_8.name());
        } catch (Exception ignored) {
            return value;
        }
    }

    private static String encodeCookie(String value) {
        try {
            return URLEncoder.encode(value, StandardCharsets.UTF_8.name());
        } catch (Exception ignored) {
            return value;
        }
    }
}
