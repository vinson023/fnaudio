package com.fnaudio.client.playback;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.net.wifi.WifiManager;
import android.webkit.CookieManager;
import android.util.Log;
import android.graphics.Bitmap;

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
import java.io.ByteArrayOutputStream;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.RejectedExecutionException;
import java.util.Set;
import java.util.ArrayList;
import java.util.HashSet;
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
import okhttp3.ResponseBody;

@OptIn(markerClass = UnstableApi.class)
public final class PlaybackService extends MediaSessionService {
    private static final String TAG = "fnAudioPlayback";
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
    public static final String EXTRA_SESSION_GENERATION = "session_generation";
    public static final String EXTRA_ENGINE_EPOCH = "engine_epoch";

    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    // The WebView receives server-sent state while it is active. Native
    // polling is only a background/suspended-WebView recovery path.
    private static final long REMOTE_POLL_INTERVAL_MS = 5000L;
    private static final long REMOTE_BRIDGE_GRACE_MS = 4500L;
    private static final long REMOTE_EVENT_RETRY_MS = 1000L;
    private static final int MAX_REMOTE_EVENT_BYTES = 512 * 1024;
    private static final String REMOTE_NOTIFICATION_CHANNEL = "fnaudio_remote_playback";
    private static final int REMOTE_NOTIFICATION_ID = 7011;
    private static final String REMOTE_SESSION_PREFS = "fnaudio_remote_session";
    private static final String REMOTE_SESSION_KEY = "snapshot";
    private static final int MAX_PERSISTED_QUEUE_BYTES = 512 * 1024;
    private static final int MAX_NOTIFICATION_ARTWORK_BYTES = 2 * 1024 * 1024;
    private static final int MAX_REMOTE_RESPONSE_BYTES = 512 * 1024;
    private static final int MAX_REMOTE_COMMAND_CALLS = 16;
    private static final int MAX_REMOTE_QUEUE_ITEMS = 500;
    private static final int MAX_REMOTE_METADATA_CHARS = 512;
    private static final int MAX_REMOTE_TARGET_ID_CHARS = 256;
    private static final int MAX_REMOTE_TARGET_NAME_CHARS = 512;
    private static final int MAX_REMOTE_QUEUE_JSON_CHARS = 512 * 1024;
    private static final long MAX_REMOTE_DURATION_MS = 24L * 60L * 60L * 1000L;
    private static final long MAX_PERSISTED_SESSION_AGE_MS = 7L * 24L * 60L * 60L * 1000L;
    private static final int PERSISTED_SESSION_SCHEMA = 1;

    private ExoPlayer player;
    private RemotePlaybackPlayer remotePlayer;
    private MediaSession mediaSession;
    /** Keeps remote/DLNA playback alive while the WebView task is backgrounded. */
    @Nullable private PowerManager.WakeLock remoteWakeLock;
    @Nullable private WifiManager.WifiLock remoteWifiLock;
    private AuthenticatedBitmapLoader bitmapLoader;
    private ConnectionProfile profile;
    private OkHttpClient httpClient;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private volatile String remoteTargetId = "";
    private volatile String remoteTargetName = "";
    private volatile boolean remotePollInFlight;
    private volatile long remoteBridgeUpdateAt;
    @Nullable private volatile Call remoteStatusCall;
    @Nullable private volatile Call remoteEventCall;
    private final Object remoteCommandLock = new Object();
    private final Set<Call> remoteCommandCalls = new HashSet<>();
    private volatile boolean remoteEventConnected;
    private volatile long remoteSessionGeneration;
    private volatile long remoteEngineEpoch;
    private volatile boolean destroyed;
    // A foreground service start carrying an explicit command wins over the
    // restore task queued during onCreate(). Without this gate, a new WebView
    // session can be replaced by the previous process snapshot a moment later.
    private boolean remoteRestoreAllowed = true;
    private long remoteLastStateVersion;
    private final Runnable remotePoll = this::pollRemoteStatus;
    private final Runnable remoteEventRetry = this::startRemoteEventStream;
    private final Runnable remoteRestore = this::restorePersistedRemoteSession;

    @Override
    public void onCreate() {
        super.onCreate();
        destroyed = false;
        Log.i(TAG, "session_create begin");
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

        httpClient = HttpClientFactory.createMediaClient(this, profile);
        OkHttpDataSource.Factory dataSourceFactory = new OkHttpDataSource.Factory(httpClient)
                .setUserAgent("fnAudio-Android");

        player = new ExoPlayer.Builder(this)
                .setMediaSourceFactory(new DefaultMediaSourceFactory(dataSourceFactory))
                .build();
        player.setAudioAttributes(AudioAttributes.DEFAULT, true);
        player.setHandleAudioBecomingNoisy(true);
        player.setWakeMode(C.WAKE_MODE_LOCAL);
        remotePlayer = new RemotePlaybackPlayer(Looper.getMainLooper(), this::sendRemoteCommand);
        bitmapLoader = new AuthenticatedBitmapLoader(this, profile, httpClient);
        Intent openPlayback = new Intent(this, MainActivity.class)
                .setAction(MainActivity.ACTION_OPEN_PLAYBACK)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent sessionActivity = PendingIntent.getActivity(
                this,
                0,
                openPlayback,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        mediaSession = new MediaSession.Builder(this, player)
                .setBitmapLoader(bitmapLoader)
                .setSessionActivity(sessionActivity)
                .build();
        Log.i(TAG, "session_ready media_session");
        PowerManager powerManager = (PowerManager) getSystemService(POWER_SERVICE);
        if (powerManager != null) {
            remoteWakeLock = powerManager.newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK,
                    "fnAudio:remote-playback"
            );
            remoteWakeLock.setReferenceCounted(false);
        }
        WifiManager wifiManager = (WifiManager) getApplicationContext().getSystemService(WIFI_SERVICE);
        if (wifiManager != null) {
            try {
                remoteWifiLock = wifiManager.createWifiLock(
                        WifiManager.WIFI_MODE_FULL_HIGH_PERF,
                        "fnAudio:remote-network-playback"
                );
                remoteWifiLock.setReferenceCounted(false);
            } catch (RuntimeException ignored) {
                remoteWifiLock = null;
            }
        }
        mainHandler.post(remoteRestore);
    }

    @Override
    public int onStartCommand(@Nullable Intent intent, int flags, int startId) {
        if (intent != null) {
            String action = intent.getAction();
            if (ACTION_REMOTE_ENABLE.equals(action) || ACTION_REMOTE_UPDATE.equals(action)
                    || ACTION_LOCAL_ENABLE.equals(action)) {
                remoteRestoreAllowed = false;
                mainHandler.removeCallbacks(remoteRestore);
            }
            if (ACTION_REMOTE_ENABLE.equals(action)) enableRemoteMode(intent);
            else if (ACTION_REMOTE_UPDATE.equals(action)) updateRemoteMode(intent);
            else if (ACTION_LOCAL_ENABLE.equals(action)) enableLocalMode();
            else if (action != null) Log.w(TAG, "service_start ignored: unknown_action");
        }
        // A remote renderer has no local decoder to keep the service alive.
        // START_STICKY mirrors the official host application's service policy
        // and lets Android recreate the session after process reclaim.
        super.onStartCommand(intent, flags, startId);
        return START_STICKY;
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
        if (remotePlayer != null && remotePlayer.isRemoteActive()) {
            // Do not tear down an active remote session when the WebView task
            // is swiped away. Re-assert foreground state and let the backend
            // remain authoritative for next-track progression.
            persistRemoteStatus();
            ensureRemoteForeground();
            super.onTaskRemoved(rootIntent);
            return;
        }
        if (player == null || !player.getPlayWhenReady() || player.getPlaybackState() == Player.STATE_ENDED) {
            stopSelf();
        }
        super.onTaskRemoved(rootIntent);
    }

    @Override
    public void onDestroy() {
        destroyed = true;
        if (remotePlayer != null && remotePlayer.isRemoteActive()) {
            // Persist before releasing the metadata-only player so a process
            // reclaim can restore the last confirmed remote position.
            persistRemoteStatus(true);
            Log.i(TAG, "remote_session_restore checkpointed: service_destroy");
        }
        mainHandler.removeCallbacks(remotePoll);
        mainHandler.removeCallbacks(remoteEventRetry);
        mainHandler.removeCallbacks(remoteRestore);
        cancelRemoteCommandRequests();
        cancelRemoteStatusRequest();
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
        releaseRemoteWakeLock();
        if (httpClient != null) {
            httpClient.dispatcher().cancelAll();
            httpClient.dispatcher().executorService().shutdownNow();
            httpClient.connectionPool().evictAll();
            httpClient = null;
        }
        super.onDestroy();
    }

    private boolean enableRemoteMode(Intent intent) {
        if (destroyed || mediaSession == null || remotePlayer == null || player == null) {
            Log.w(TAG, "remote_enable rejected: session_not_ready");
            return false;
        }
        String targetId = boundedIdentity(safeStringExtra(intent, EXTRA_TARGET_ID), MAX_REMOTE_TARGET_ID_CHARS);
        if (targetId.isEmpty() || "local".equals(targetId)) {
            Log.w(TAG, "remote_enable rejected: invalid_target");
            return false;
        }
        List<MediaItem> items = parseRemoteItems(safeStringExtra(intent, EXTRA_QUEUE_JSON));
        if (items.isEmpty()) {
            Log.w(TAG, "remote_enable rejected: empty_queue");
            return false;
        }
        cancelRemoteStatusRequest();
        closeRemoteEventStream();
        cancelRemoteCommandRequests();
        remoteTargetId = targetId;
        remoteSessionGeneration = boundedCounter(safeLongExtra(intent, EXTRA_SESSION_GENERATION, 0L));
        remoteEngineEpoch = boundedCounter(safeLongExtra(intent, EXTRA_ENGINE_EPOCH, 0L));
        remoteLastStateVersion = 0L;
        remoteTargetName = boundedText(safeStringExtra(intent, EXTRA_TARGET_NAME), MAX_REMOTE_TARGET_NAME_CHARS);
        player.pause();
        player.stop();
        remotePlayer.activate(
                items,
                safeIntExtra(intent, EXTRA_INDEX, 0),
                safeLongExtra(intent, EXTRA_POSITION_MS, 0L),
                safeLongExtra(intent, EXTRA_DURATION_MS, 0L),
                safeBooleanExtra(intent, EXTRA_PLAYING, false),
                safeIntExtra(intent, EXTRA_REPEAT_MODE, Player.REPEAT_MODE_OFF),
                safeBooleanExtra(intent, EXTRA_SHUFFLE, false)
        );
        if (mediaSession.getPlayer() != remotePlayer) mediaSession.setPlayer(remotePlayer);
        acquireRemoteWakeLock();
        ensureRemoteForeground();
        remoteBridgeUpdateAt = SystemClock.elapsedRealtime();
        startRemoteEventStream();
        scheduleRemotePoll(REMOTE_BRIDGE_GRACE_MS + 250L);
        persistRemoteSession(items, intent);
        Log.i(TAG, "remote_enable ready: items=" + items.size());
        return true;
    }

    private void updateRemoteMode(Intent intent) {
        if (remotePlayer == null || !remotePlayer.isRemoteActive()) {
            Log.w(TAG, "remote_update ignored: session_inactive");
            return;
        }
        String targetId = boundedIdentity(safeStringExtra(intent, EXTRA_TARGET_ID), MAX_REMOTE_TARGET_ID_CHARS);
        if (!targetId.isEmpty() && !targetId.equals(remoteTargetId)) {
            Log.d(TAG, "remote_update ignored: stale_target");
            return;
        }
        if (remoteEventConnected) return;
        Long updateGeneration = intentCounter(intent, EXTRA_SESSION_GENERATION);
        Long updateEngineEpoch = intentCounter(intent, EXTRA_ENGINE_EPOCH);
        if ((intent.hasExtra(EXTRA_SESSION_GENERATION) && updateGeneration == null)
                || (intent.hasExtra(EXTRA_ENGINE_EPOCH) && updateEngineEpoch == null)) {
            Log.w(TAG, "remote_update failed: invalid_payload");
            return;
        }
        if ((remoteSessionGeneration > 0L && updateGeneration == null)
                || (remoteEngineEpoch > 0L && updateEngineEpoch == null)) {
            Log.d(TAG, "remote_update ignored: missing_session_identity");
            return;
        }
        if (updateGeneration != null && updateGeneration != remoteSessionGeneration) {
            Log.d(TAG, "remote_update ignored: stale_generation");
            return;
        }
        if (updateEngineEpoch != null && updateEngineEpoch != remoteEngineEpoch) {
            Log.d(TAG, "remote_update ignored: stale_engine_epoch");
            return;
        }
        remotePlayer.updateStatus(
                safeIntExtra(intent, EXTRA_INDEX, remotePlayer.getCurrentMediaItemIndex()),
                safeLongExtra(intent, EXTRA_POSITION_MS, Math.max(0L, remotePlayer.getCurrentPosition())),
                safeLongExtra(intent, EXTRA_DURATION_MS, Math.max(0L, remotePlayer.getDuration())),
                safeBooleanExtra(intent, EXTRA_PLAYING, remotePlayer.isRemotePlaying())
        );
        remoteBridgeUpdateAt = SystemClock.elapsedRealtime();
        ensureRemoteForeground();
        persistRemoteStatus();
        Log.d(TAG, "remote_update applied");
    }

    @Nullable
    private static Long intentCounter(Intent intent, String key) {
        if (intent == null || !intent.hasExtra(key)) return null;
        try {
            Object raw = intent.getExtras() == null ? null : intent.getExtras().get(key);
            if (!(raw instanceof Long)) return null;
            long value = (Long) raw;
            return value < 0L ? null : boundedCounter(value);
        } catch (RuntimeException ignored) {
            return null;
        }
    }

    private static int safeIntExtra(@Nullable Intent intent, String key, int fallback) {
        try { return intent == null ? fallback : intent.getIntExtra(key, fallback); }
        catch (RuntimeException ignored) { return fallback; }
    }

    private static long safeLongExtra(@Nullable Intent intent, String key, long fallback) {
        try { return intent == null ? fallback : intent.getLongExtra(key, fallback); }
        catch (RuntimeException ignored) { return fallback; }
    }

    private static boolean safeBooleanExtra(@Nullable Intent intent, String key, boolean fallback) {
        try { return intent == null ? fallback : intent.getBooleanExtra(key, fallback); }
        catch (RuntimeException ignored) { return fallback; }
    }

    private static String safeStringExtra(@Nullable Intent intent, String key) {
        try {
            String value = intent == null ? null : intent.getStringExtra(key);
            return value == null ? "" : value;
        } catch (RuntimeException ignored) {
            return "";
        }
    }

    private void enableLocalMode() {
        mainHandler.removeCallbacks(remotePoll);
        mainHandler.removeCallbacks(remoteEventRetry);
        cancelRemoteStatusRequest();
        cancelRemoteCommandRequests();
        remoteTargetId = "";
        remoteTargetName = "";
        remoteLastStateVersion = 0L;
        remotePollInFlight = false;
        remoteBridgeUpdateAt = 0L;
        clearPersistedRemoteSession();
        closeRemoteEventStream();
        if (remotePlayer != null) remotePlayer.deactivate();
        if (mediaSession != null && player != null && mediaSession.getPlayer() != player) mediaSession.setPlayer(player);
        releaseRemoteWakeLock();
        stopForeground(true);
        Log.i(TAG, "local_mode enabled");
    }

    private void ensureRemoteForeground() {
        if (mediaSession == null || remotePlayer == null || !remotePlayer.isRemoteActive()) return;
        acquireRemoteWakeLock();
        publishRemoteMediaNotification();
    }

    private void acquireRemoteWakeLock() {
        PowerManager.WakeLock wakeLock = remoteWakeLock;
        if (wakeLock != null && !wakeLock.isHeld()) {
            try {
                wakeLock.acquire();
            } catch (RuntimeException ignored) {
                // Some vendor builds can reject a wake-lock after shutdown.
            }
        }
        WifiManager.WifiLock wifiLock = remoteWifiLock;
        if (wifiLock != null && !wifiLock.isHeld()) {
            try {
                wifiLock.acquire();
            } catch (RuntimeException ignored) {
            }
        }
    }

    private void releaseRemoteWakeLock() {
        PowerManager.WakeLock wakeLock = remoteWakeLock;
        if (wakeLock != null && wakeLock.isHeld()) {
            try {
                wakeLock.release();
            } catch (RuntimeException ignored) {
            }
        }
        WifiManager.WifiLock wifiLock = remoteWifiLock;
        if (wifiLock != null && wifiLock.isHeld()) {
            try {
                wifiLock.release();
            } catch (RuntimeException ignored) {
            }
        }
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
        Bitmap artwork = decodeNotificationArtwork(metadata.artworkData);
        if (artwork != null) builder.setLargeIcon(artwork);
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
        try {
            startForeground(REMOTE_NOTIFICATION_ID, notification);
            Log.d(TAG, "remote_notification published");
        } catch (RuntimeException ignored) {
            Log.w(TAG, "remote_notification failed: publish");
        }
    }

    @Nullable
    private Bitmap decodeNotificationArtwork(@Nullable byte[] artworkData) {
        if (artworkData == null || artworkData.length == 0 || artworkData.length > MAX_NOTIFICATION_ARTWORK_BYTES) {
            return null;
        }
        try {
            return ArtworkBitmapDecoder.decode(artworkData);
        } catch (RuntimeException ignored) {
            Log.w(TAG, "remote_notification artwork failed: invalid_payload");
            return null;
        }
    }

    private void persistRemoteSession(List<MediaItem> items, Intent intent) {
        try {
            String queue = safeStringExtra(intent, EXTRA_QUEUE_JSON);
            if (queue == null || queue.getBytes(StandardCharsets.UTF_8).length > MAX_PERSISTED_QUEUE_BYTES) return;
            JSONObject snapshot = new JSONObject();
            snapshot.put("schema", PERSISTED_SESSION_SCHEMA);
            snapshot.put("saved_at_ms", System.currentTimeMillis());
            snapshot.put("target_id", remoteTargetId);
            snapshot.put("target_name", remoteTargetName);
            snapshot.put("queue_json", queue);
            snapshot.put("index", safeIntExtra(intent, EXTRA_INDEX, 0));
            snapshot.put("position_ms", safeLongExtra(intent, EXTRA_POSITION_MS, 0L));
            snapshot.put("duration_ms", safeLongExtra(intent, EXTRA_DURATION_MS, 0L));
            snapshot.put("playing", safeBooleanExtra(intent, EXTRA_PLAYING, false));
            snapshot.put("repeat_mode", safeIntExtra(intent, EXTRA_REPEAT_MODE, Player.REPEAT_MODE_OFF));
            snapshot.put("shuffle", safeBooleanExtra(intent, EXTRA_SHUFFLE, false));
            snapshot.put("generation", remoteSessionGeneration);
            snapshot.put("engine_epoch", remoteEngineEpoch);
            getSharedPreferences(REMOTE_SESSION_PREFS, MODE_PRIVATE).edit().putString(REMOTE_SESSION_KEY, snapshot.toString()).apply();
        } catch (Exception ignored) {
            Log.w(TAG, "remote_session_persist failed: invalid_snapshot");
        }
    }

    private void persistRemoteStatus() {
        persistRemoteStatus(false);
    }

    private void persistRemoteStatus(boolean synchronous) {
        SharedPreferences preferences = getSharedPreferences(REMOTE_SESSION_PREFS, MODE_PRIVATE);
        String raw = preferences.getString(REMOTE_SESSION_KEY, "");
        if (raw == null || raw.isEmpty() || remotePlayer == null) return;
        try {
            JSONObject snapshot = new JSONObject(raw);
            snapshot.put("index", remotePlayer.getCurrentMediaItemIndex());
            snapshot.put("position_ms", Math.max(0L, remotePlayer.getCurrentPosition()));
            snapshot.put("duration_ms", Math.max(0L, remotePlayer.getDuration()));
            snapshot.put("playing", remotePlayer.isRemotePlaying());
            SharedPreferences.Editor editor = preferences.edit().putString(REMOTE_SESSION_KEY, snapshot.toString());
            if (synchronous) {
                if (!editor.commit()) Log.w(TAG, "remote_session_restore checkpoint failed: commit");
            } else {
                editor.apply();
            }
        } catch (Exception ignored) {
            clearPersistedRemoteSession();
        }
    }

    private void clearPersistedRemoteSession() {
        getSharedPreferences(REMOTE_SESSION_PREFS, MODE_PRIVATE).edit().remove(REMOTE_SESSION_KEY).apply();
    }

    private void restorePersistedRemoteSession() {
        if (!remoteRestoreAllowed || destroyed || mediaSession == null || remotePlayer == null || player == null) return;
        remoteRestoreAllowed = false;
        String raw = getSharedPreferences(REMOTE_SESSION_PREFS, MODE_PRIVATE).getString(REMOTE_SESSION_KEY, "");
        if (raw == null || raw.isEmpty()) return;
        if (raw.getBytes(StandardCharsets.UTF_8).length > MAX_PERSISTED_QUEUE_BYTES + 4096) {
            clearPersistedRemoteSession();
            Log.w(TAG, "remote_session_restore failed: invalid_snapshot oversized");
            return;
        }
        try {
            JSONObject snapshot = new JSONObject(raw);
            if (persistedInt(snapshot, "schema", 0) != PERSISTED_SESSION_SCHEMA) {
                clearPersistedRemoteSession();
                Log.w(TAG, "remote_session_restore failed: invalid_snapshot schema");
                return;
            }
            long savedAt = persistedLong(snapshot, "saved_at_ms", 0L);
            long age = System.currentTimeMillis() - savedAt;
            if (savedAt <= 0L || age < 0L || age > MAX_PERSISTED_SESSION_AGE_MS) {
                clearPersistedRemoteSession();
                Log.i(TAG, "remote_session_restore skipped: expired_snapshot");
                return;
            }
            String target = boundedIdentity(persistedString(snapshot, "target_id", ""), MAX_REMOTE_TARGET_ID_CHARS);
            String queue = persistedString(snapshot, "queue_json", "");
            if (target.isEmpty() || "local".equals(target) || queue.isEmpty()
                    || queue.getBytes(StandardCharsets.UTF_8).length > MAX_PERSISTED_QUEUE_BYTES) {
                clearPersistedRemoteSession();
                Log.w(TAG, "remote_session_restore failed: invalid_snapshot payload");
                return;
            }
            Intent intent = new Intent().putExtra(EXTRA_TARGET_ID, target)
                    .putExtra(EXTRA_TARGET_NAME, boundedText(persistedString(snapshot, "target_name", ""), MAX_REMOTE_TARGET_NAME_CHARS))
                    .putExtra(EXTRA_QUEUE_JSON, queue)
                    .putExtra(EXTRA_INDEX, persistedInt(snapshot, "index", 0))
                    .putExtra(EXTRA_POSITION_MS, Math.max(0L, persistedLong(snapshot, "position_ms", 0L)))
                    .putExtra(EXTRA_DURATION_MS, Math.max(0L, persistedLong(snapshot, "duration_ms", 0L)))
                    .putExtra(EXTRA_PLAYING, persistedBoolean(snapshot, "playing", false))
                    .putExtra(EXTRA_REPEAT_MODE, persistedInt(snapshot, "repeat_mode", Player.REPEAT_MODE_OFF))
                    .putExtra(EXTRA_SHUFFLE, persistedBoolean(snapshot, "shuffle", false))
                    .putExtra(EXTRA_SESSION_GENERATION, boundedCounter(persistedLong(snapshot, "generation", 0L)))
                    // A recreated service is a new local engine. Advance the
                    // epoch before reconnecting so delayed events from the
                    // previous process cannot overwrite the restored state.
                    .putExtra(EXTRA_ENGINE_EPOCH, nextCounter(persistedLong(snapshot, "engine_epoch", 0L)));
            if (enableRemoteMode(intent)) {
                Log.i(TAG, "remote_session_restore ready");
            } else {
                clearPersistedRemoteSession();
                Log.w(TAG, "remote_session_restore failed: activation_rejected");
            }
        } catch (Exception ignored) {
            clearPersistedRemoteSession();
            Log.w(TAG, "remote_session_restore failed: invalid_snapshot");
        }
    }

    private void sendRemoteCommand(String action, @Nullable Long positionMs, @Nullable String requestedTrackId, long requestToken) {
        if (remoteTargetId.isEmpty() || profile == null || httpClient == null) {
            Log.w(TAG, "remote_command rejected: session_unavailable action=" + clean(action));
            clearPendingCommandIfCurrent(
                    action, requestToken, remoteTargetId, remoteSessionGeneration, remoteEngineEpoch
            );
            return;
        }
        final String commandTargetId = remoteTargetId;
        final long commandGeneration = remoteSessionGeneration;
        final long commandEngineEpoch = remoteEngineEpoch;
        final String commandId = "android-" + UUID.randomUUID();
        JSONObject payload = new JSONObject();
        try {
            payload.put("target_id", commandTargetId);
            payload.put("action", action);
            payload.put("command_id", commandId);
            payload.put("generation", commandGeneration);
            payload.put("engine_epoch", commandEngineEpoch);
            if (positionMs != null) payload.put("position", Math.max(0L, positionMs) / 1000d);
            String trackId = clean(requestedTrackId);
            if (trackId.isEmpty()) {
                MediaItem current = remotePlayer == null ? null : remotePlayer.currentRemoteItem();
                if (current != null) trackId = current.mediaId;
            }
            if (!trackId.isEmpty()) payload.put("track_id", trackId);
            if ("repeat".equals(action) && remotePlayer != null) {
                payload.put("repeat", repeatName(remotePlayer.getRequestedRepeatMode()));
            } else if ("shuffle".equals(action) && remotePlayer != null) {
                payload.put("shuffle", remotePlayer.isRequestedShuffleEnabled());
            }
        } catch (Exception ignored) {
            clearPendingCommandIfCurrent(
                    action, requestToken, commandTargetId, commandGeneration, commandEngineEpoch
            );
            return;
        }
        Request request = authenticatedRequest(profile.fnAudioUrl() + "api/playback/control")
                .post(RequestBody.create(payload.toString(), JSON))
                .build();
        Call commandCall = httpClient.newCall(request);
        if (!trackRemoteCommandCall(commandCall)) {
            Log.w(TAG, "remote_command rejected: too_many_in_flight");
            clearPendingCommandIfCurrent(action, requestToken, commandTargetId, commandGeneration, commandEngineEpoch);
            return;
        }
        try {
            commandCall.enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException exception) {
                completeRemoteCommandCall(call);
                if (call.isCanceled()) {
                    Log.d(TAG, "remote_command ended: cancelled");
                } else {
                    Log.w(TAG, "remote_command failed: network");
                }
                clearPendingCommandIfCurrent(action, requestToken, commandTargetId, commandGeneration, commandEngineEpoch);
                if (remoteCommandStillCurrent(commandTargetId, commandGeneration, commandEngineEpoch)) {
                    scheduleRemotePoll(300L);
                }
            }

            @Override
            public void onResponse(Call call, Response response) {
                boolean success = response.isSuccessful();
                boolean applied = false;
                try (Response ignored = response) {
                    if (response.body() != null && remoteCommandStillCurrent(
                            commandTargetId, commandGeneration, commandEngineEpoch)) {
                        JSONObject data = new JSONObject(readBoundedBody(response.body(), MAX_REMOTE_RESPONSE_BYTES));
                        if (success && sessionIdentityMatches(data, "remote_command") && commandTicketMatches(data)) {
                            if (data.has("transport") || data.has("position")) applyRemoteStatus(data);
                            applyRemoteCore(data.optJSONObject("core"));
                            applied = true;
                        }
                    }
                } catch (Exception ignored) {
                }
                completeRemoteCommandCall(call);
                // Notification actions can arrive while WebView is suspended.
                // Force one authoritative refresh after their command result.
                boolean current = remoteCommandStillCurrent(
                        commandTargetId, commandGeneration, commandEngineEpoch
                );
                if (current) remoteBridgeUpdateAt = 0L;
                if (success && applied) {
                    Log.d(TAG, "remote_command confirmed: action=" + clean(action));
                    // A paused snapshot also has playing=false, so it is not
                    // sufficient evidence that a deduplicated stop command
                    // completed. The ticket-bound response is authoritative.
                    if ("stop".equals(action)) {
                        clearPendingCommandIfCurrent(
                                action, requestToken, commandTargetId, commandGeneration, commandEngineEpoch
                        );
                    }
                } else if (success) {
                    Log.w(TAG, "remote_command failed: stale_response");
                    clearPendingCommandIfCurrent(action, requestToken, commandTargetId, commandGeneration, commandEngineEpoch);
                } else {
                    Log.w(TAG, "remote_command failed: http_" + response.code());
                    clearPendingCommandIfCurrent(action, requestToken, commandTargetId, commandGeneration, commandEngineEpoch);
                }
                if (current) scheduleRemotePoll(150L);
            }
            });
        } catch (RejectedExecutionException error) {
            completeRemoteCommandCall(commandCall);
            Log.d(TAG, "remote_command ended: dispatcher_closed");
            clearPendingCommandIfCurrent(action, requestToken, commandTargetId, commandGeneration, commandEngineEpoch);
            if (remoteCommandStillCurrent(commandTargetId, commandGeneration, commandEngineEpoch)) {
                scheduleRemotePoll(300L);
            }
        }
    }

    private boolean remoteCommandStillCurrent(String targetId, long generation, long engineEpoch) {
        return !destroyed && targetId != null && targetId.equals(remoteTargetId)
                && remoteSessionGeneration == generation
                && remoteEngineEpoch == engineEpoch;
    }

    private void clearPendingCommandIfCurrent(String action, long requestToken, String targetId, long generation, long engineEpoch) {
        mainHandler.post(() -> {
            if (remotePlayer != null && remoteCommandStillCurrent(targetId, generation, engineEpoch)) {
                remotePlayer.clearPendingCommand(action, requestToken);
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
        final String requestTargetId = remoteTargetId;
        final long requestGeneration = remoteSessionGeneration;
        final long requestEngineEpoch = remoteEngineEpoch;
        String url = profile.fnAudioUrl() + "api/playback/status?target_id=" + encodeQuery(requestTargetId);
        final Call requestCall = httpClient.newCall(authenticatedRequest(url).get().build());
        remoteStatusCall = requestCall;
        try {
            requestCall.enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException exception) {
                boolean ownsRequest = remoteStatusCall == call;
                if (ownsRequest) {
                    remoteStatusCall = null;
                    remotePollInFlight = false;
                }
                if (call.isCanceled()) {
                    Log.d(TAG, "remote_status ended: cancelled");
                } else {
                    Log.w(TAG, "remote_status failed: network");
                }
                if (ownsRequest && remoteRequestStillCurrent(requestTargetId, requestGeneration, requestEngineEpoch)) {
                    scheduleRemotePoll(REMOTE_POLL_INTERVAL_MS);
                }
            }

            @Override
            public void onResponse(Call call, Response response) {
                boolean ownsRequest = remoteStatusCall == call;
                try (Response ignored = response) {
                    if (response.isSuccessful() && response.body() != null
                            && ownsRequest
                            && remoteRequestStillCurrent(requestTargetId, requestGeneration, requestEngineEpoch)) {
                        applyRemoteStatus(new JSONObject(readBoundedBody(response.body(), MAX_REMOTE_RESPONSE_BYTES)));
                    } else {
                        Log.w(TAG, "remote_status failed: http_" + response.code());
                    }
                } catch (Exception ignored) {
                    Log.w(TAG, "remote_status failed: invalid_payload");
                } finally {
                    if (ownsRequest && remoteStatusCall == call) {
                        remoteStatusCall = null;
                        remotePollInFlight = false;
                    }
                    if (ownsRequest && remoteRequestStillCurrent(requestTargetId, requestGeneration, requestEngineEpoch)) {
                        scheduleRemotePoll(REMOTE_POLL_INTERVAL_MS);
                    }
                }
            }
            });
        } catch (RejectedExecutionException error) {
            if (remoteStatusCall == requestCall) {
                remoteStatusCall = null;
                remotePollInFlight = false;
            }
            Log.d(TAG, "remote_status ended: dispatcher_closed");
            if (remoteRequestStillCurrent(requestTargetId, requestGeneration, requestEngineEpoch)) {
                scheduleRemotePoll(REMOTE_POLL_INTERVAL_MS);
            }
        }
    }

    private boolean remoteRequestStillCurrent(String targetId, long generation, long engineEpoch) {
        return !destroyed
                && targetId != null && targetId.equals(remoteTargetId)
                && remoteSessionStillCurrent(generation, engineEpoch);
    }

    private void cancelRemoteStatusRequest() {
        Call call = remoteStatusCall;
        remoteStatusCall = null;
        remotePollInFlight = false;
        if (call != null) call.cancel();
    }

    private void cancelRemoteCommandRequests() {
        List<Call> calls;
        synchronized (remoteCommandLock) {
            calls = new ArrayList<>(remoteCommandCalls);
            remoteCommandCalls.clear();
        }
        for (Call call : calls) {
            call.cancel();
        }
    }

    private boolean trackRemoteCommandCall(Call call) {
        synchronized (remoteCommandLock) {
            if (remoteCommandCalls.size() >= MAX_REMOTE_COMMAND_CALLS) return false;
            remoteCommandCalls.add(call);
            return true;
        }
    }

    private void completeRemoteCommandCall(Call call) {
        synchronized (remoteCommandLock) {
            remoteCommandCalls.remove(call);
        }
    }

    private void applyRemoteStatus(JSONObject data) {
        if (data == null) {
            Log.w(TAG, "remote_status failed: invalid_payload");
            return;
        }
        if (destroyed) return;
        if (!sessionIdentityMatches(data, "remote_status")) return;
        Long parsedStateVersion = optionalCounter(data, "state_version");
        if (parsedStateVersion == null) {
            Log.w(TAG, "remote_status failed: invalid_payload");
            return;
        }
        long stateVersion = parsedStateVersion;
        final long eventGeneration = remoteSessionGeneration;
        final long eventEngineEpoch = remoteEngineEpoch;
        JSONObject transport = data.optJSONObject("transport");
        JSONObject position = data.optJSONObject("position");
        JSONObject core = data.optJSONObject("core");
        String state = stringField(transport, "state").toUpperCase(Locale.ROOT);
        boolean playing = "PLAYING".equals(state) || "TRANSITIONING".equals(state);
        long positionMs = secondsField(position, "rel_seconds", 0L);
        long durationMs = secondsField(position, "duration_seconds", 0L);
        boolean hasRepeat = data.has("repeat");
        boolean hasShuffle = data.has("shuffle");
        int repeatMode = hasRepeat ? repeatModeFromName(stringField(data, "repeat")) : Player.REPEAT_MODE_OFF;
        boolean shuffleMode = hasShuffle && booleanField(data, "shuffle", false);
        mainHandler.post(() -> {
            if (!destroyed && remotePlayer != null && remotePlayer.isRemoteActive()
                    && remoteSessionStillCurrent(eventGeneration, eventEngineEpoch)) {
                if (remoteLastStateVersion > 0L && stateVersion < remoteLastStateVersion) {
                    Log.d(TAG, "remote_status ignored: stale_state");
                    return;
                }
                if (stateVersion > remoteLastStateVersion) remoteLastStateVersion = stateVersion;
                if (hasRepeat || hasShuffle) {
                    remotePlayer.updateModes(
                            hasRepeat ? repeatMode : remotePlayer.getRemoteRepeatMode(),
                            hasShuffle ? shuffleMode : remotePlayer.isRemoteShuffleEnabled()
                    );
                }
                int index = indexFromCore(core);
                int safeIndex = index < 0 ? remotePlayer.getCurrentMediaItemIndex() : index;
                remotePlayer.updateStatus(safeIndex, positionMs, durationMs, playing);
                ensureRemoteForeground();
            }
        });
    }

    private static String readBoundedBody(@Nullable ResponseBody body, int maxBytes) throws IOException {
        if (body == null || maxBytes <= 0) throw new IOException("empty response body");
        long declared = body.contentLength();
        if (declared > maxBytes) throw new IOException("response body is too large");
        InputStream input = body.byteStream();
        ByteArrayOutputStream output = new ByteArrayOutputStream(
                (int) Math.min(Math.max(declared, 0L), maxBytes));
        byte[] buffer = new byte[8192];
        int total = 0;
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (count == 0) continue;
            if (count > maxBytes - total) throw new IOException("response body is too large");
            output.write(buffer, 0, count);
            total += count;
        }
        return output.toString(StandardCharsets.UTF_8.name());
    }

    private boolean sessionIdentityMatches(@Nullable JSONObject data, String source) {
        if (data == null) return false;
        Long generation = optionalCounter(data, "generation");
        Long engineEpoch = optionalCounter(data, "engine_epoch");
        if ((remoteSessionGeneration > 0L && !data.has("generation"))
                || (remoteEngineEpoch > 0L && !data.has("engine_epoch"))) {
            Log.w(TAG, source + " failed: invalid_payload");
            return false;
        }
        if ((data.has("generation") && generation == null)
                || (data.has("engine_epoch") && engineEpoch == null)) {
            Log.w(TAG, source + " failed: invalid_payload");
            return false;
        }
        if (data.has("generation") && generation != remoteSessionGeneration) {
            Log.d(TAG, "remote_status".equals(source) ? "remote_status ignored: stale_generation" : source + " ignored: stale_generation");
            return false;
        }
        if (data.has("engine_epoch") && engineEpoch != remoteEngineEpoch) {
            Log.d(TAG, "remote_status".equals(source) ? "remote_status ignored: stale_engine_epoch" : source + " ignored: stale_engine_epoch");
            return false;
        }
        return true;
    }

    @Nullable
    private static Long optionalCounter(JSONObject data, String key) {
        if (data == null || !data.has(key)) return 0L;
        Object raw = data.opt(key);
        if (raw instanceof Boolean || raw == null) return null;
        try {
            if (raw instanceof Number) {
                double numeric = ((Number) raw).doubleValue();
                if (Double.isNaN(numeric) || Double.isInfinite(numeric) || numeric < 0d
                        || numeric != Math.rint(numeric)) return null;
                return boundedCounter(((Number) raw).longValue());
            }
            if (raw instanceof String) {
                String text = ((String) raw).trim();
                if (text.isEmpty() || !text.matches("[0-9]+")) return null;
                return boundedCounter(Long.parseLong(text));
            }
        } catch (RuntimeException ignored) {
            return null;
        }
        return null;
    }

    private boolean commandTicketMatches(@Nullable JSONObject data) {
        if (data == null || !data.has("command_id")) return true;
        String commandId = clean(stringField(data, "command_id"));
        JSONObject core = data.optJSONObject("core");
        String ticket = clean(stringField(core, "command_ticket"));
        // Presence of command_id opts the response into strict ticket binding.
        // An empty command id must not silently downgrade to a legacy response:
        // malformed confirmations could otherwise clear pending controls or
        // overwrite the current session with an unrelated response.
        if (commandId.isEmpty() || ticket.isEmpty() || !commandId.equals(ticket)) {
            Log.d(TAG, "remote_command ignored: stale_command_ticket");
            return false;
        }
        return true;
    }

    private void applyRemoteCore(@Nullable JSONObject core) {
        final long eventGeneration = remoteSessionGeneration;
        final long eventEngineEpoch = remoteEngineEpoch;
        mainHandler.post(() -> {
                if (!destroyed && remotePlayer != null && remotePlayer.isRemoteActive()
                        && remoteSessionStillCurrent(eventGeneration, eventEngineEpoch)) {
                    int index = indexFromCore(core);
                    if (index < 0) return;
                    long positionMs = secondsField(core, "position", 0L);
                    long durationMs = secondsField(core, "duration", remotePlayer.getDuration());
                    boolean playing = core.has("playing")
                            ? booleanField(core, "playing", false)
                            : remotePlayer.isRemotePlaying();
                    remotePlayer.updateStatus(index, positionMs, durationMs, playing);
                    persistRemoteStatus();
                    ensureRemoteForeground();
                }
        });
    }

    private boolean remoteSessionStillCurrent(long generation, long engineEpoch) {
        return remoteSessionGeneration == generation && remoteEngineEpoch == engineEpoch;
    }

    private int indexFromCore(@Nullable JSONObject core) {
        if (core == null || remotePlayer == null) return -1;
        String current = stringField(core, "current");
        if (current.isEmpty()) return -1;
        for (int i = 0; i < remotePlayer.getMediaItemCount(); i++) {
            if (current.equals(remotePlayer.getMediaItemAt(i).mediaId)) return i;
        }
        return -1;
    }

    private void scheduleRemotePoll(long delayMs) {
        mainHandler.removeCallbacks(remotePoll);
        if (destroyed) return;
        mainHandler.postDelayed(remotePoll, Math.max(0L, delayMs));
    }

    private void startRemoteEventStream() {
        mainHandler.removeCallbacks(remoteEventRetry);
        if (destroyed || remoteTargetId.isEmpty() || profile == null || httpClient == null
                || remotePlayer == null || !remotePlayer.isRemoteActive()) return;
        closeRemoteEventStream();
        final String targetId = remoteTargetId;
        final long eventGeneration = remoteSessionGeneration;
        final long eventEngineEpoch = remoteEngineEpoch;
        String url = profile.fnAudioUrl() + "api/playback/events?target_id=" + encodeQuery(targetId);
        Call call = httpClient.newCall(authenticatedRequest(url)
                .header("Accept", "text/event-stream")
                .get()
                .build());
        remoteEventCall = call;
        try {
            call.enqueue(new Callback() {
            @Override
            public void onFailure(Call failed, IOException exception) {
                if (failed.isCanceled()) {
                    Log.d(TAG, "remote_event_stream ended: cancelled");
                } else {
                    Log.w(TAG, "remote_event_stream failed: network");
                }
                onRemoteEventStreamEnded(call);
            }

            @Override
            public void onResponse(Call activeCall, Response response) {
                try (Response ignored = response) {
                    if (!response.isSuccessful() || response.body() == null) {
                        Log.w(TAG, "remote_event_stream failed: http_" + response.code());
                        return;
                    }
                    // HTTP headers alone do not prove that the proxy is
                    // delivering valid SSE frames. Keep fallback polling
                    // active until the first target- and session-matched
                    // snapshot is parsed successfully.
                    Log.d(TAG, "remote_event_stream opened");
                    readRemoteEventStream(activeCall, response, targetId, eventGeneration, eventEngineEpoch);
                } catch (Exception ignored) {
                    Log.w(TAG, "remote_event_stream failed: invalid_payload");
                } finally {
                    onRemoteEventStreamEnded(activeCall);
                }
            }
            });
        } catch (RejectedExecutionException error) {
            Log.d(TAG, "remote_event_stream ended: dispatcher_closed");
            onRemoteEventStreamEnded(call);
        }
    }

    private void readRemoteEventStream(
            Call call,
            Response response,
            String targetId,
            long generation,
            long engineEpoch
    ) throws IOException {
        StringBuilder data = new StringBuilder();
        int dataBytes = 0;
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(response.body().byteStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = readBoundedLine(reader, MAX_REMOTE_EVENT_BYTES)) != null) {
                if (call != remoteEventCall || !remoteRequestStillCurrent(targetId, generation, engineEpoch)) return;
                if (line.startsWith("data:")) {
                    String fragment = line.substring(5).trim();
                    if (data.length() > 0) {
                        data.append('\n');
                        dataBytes += 1;
                    }
                    data.append(fragment);
                    dataBytes += fragment.getBytes(StandardCharsets.UTF_8).length;
                    if (dataBytes > MAX_REMOTE_EVENT_BYTES) {
                        data.setLength(0);
                        dataBytes = 0;
                        Log.w(TAG, "remote_event_stream failed: oversized_payload");
                    }
                    continue;
                }
                if (!line.isEmpty() || data.length() == 0) continue;
                try {
                    JSONObject snapshot = new JSONObject(data.toString());
                    if (!targetId.equals(stringField(snapshot, "target_id"))
                            || !remoteRequestStillCurrent(targetId, generation, engineEpoch)) continue;
                    remoteEventConnected = true;
                    remoteBridgeUpdateAt = SystemClock.elapsedRealtime();
                    applyRemoteStatus(snapshot);
                } catch (Exception ignored) {
                    Log.w(TAG, "remote_event_stream failed: invalid_payload");
                } finally {
                    data.setLength(0);
                    dataBytes = 0;
                }
            }
        }
    }

    private static String readBoundedLine(BufferedReader reader, int maxChars) throws IOException {
        StringBuilder line = new StringBuilder();
        // Do not read a block and return on its first newline: BufferedReader
        // can deliver several SSE lines in one read, and discarding the tail
        // silently drops whole playback events. Reading one bounded character
        // at a time keeps ownership of every character with the reader.
        char[] character = new char[1];
        while (true) {
            int count = reader.read(character, 0, 1);
            if (count < 0) return line.length() == 0 ? null : line.toString();
            if (count == 0) continue;
            char value = character[0];
            if (value == '\n') return line.toString();
            if (value != '\r') {
                if (line.length() >= maxChars) throw new IOException("remote event line is too large");
                line.append(value);
            }
        }
    }

    private void onRemoteEventStreamEnded(Call call) {
        if (call != remoteEventCall) return;
        remoteEventConnected = false;
        remoteEventCall = null;
        scheduleRemotePoll(250L);
        if (!destroyed) mainHandler.postDelayed(remoteEventRetry, REMOTE_EVENT_RETRY_MS);
    }

    private void closeRemoteEventStream() {
        Call call = remoteEventCall;
        remoteEventCall = null;
        remoteEventConnected = false;
        if (call != null) call.cancel();
    }

    private static long boundedCounter(long value) {
        return Math.max(0L, Math.min(value, 2147483647L));
    }

    private static long nextCounter(long value) {
        long bounded = boundedCounter(value);
        return bounded >= 2147483647L ? bounded : bounded + 1L;
    }

    private Request.Builder authenticatedRequest(String url) {
        Request.Builder request = new Request.Builder().url(url);
        if (profile != null && !profile.webSession && !profile.token.isEmpty()) {
            String encodedToken = encodeCookie(profile.token);
            request.header("Authorization", "Bearer " + profile.token)
                    .header("X-Fnaudio-Trim-Token", profile.token)
                    .header("Cookie", "fnaudio_trim_token=" + encodedToken + "; trim_token=" + encodedToken + "; token=" + encodedToken);
        } else if (profile != null && profile.webSession) {
            // FN Connect uses the WebView session cookie instead of an fnOS token.
            String cookie = CookieManager.getInstance().getCookie(url);
            if (cookie != null && !cookie.trim().isEmpty()) request.header("Cookie", cookie);
        }
        return request;
    }

    private List<MediaItem> parseRemoteItems(@Nullable String json) {
        List<MediaItem> items = new ArrayList<>();
        Uri fallbackArtwork = Uri.fromFile(new File(getFilesDir(), "media_placeholder_white.png"));
        try {
            String queueJson = json == null ? "[]" : json;
            if (queueJson.length() > MAX_REMOTE_QUEUE_JSON_CHARS) return items;
            JSONArray array = new JSONArray(queueJson);
            int itemCount = Math.min(array.length(), MAX_REMOTE_QUEUE_ITEMS);
            for (int i = 0; i < itemCount; i++) {
                JSONObject row = array.optJSONObject(i);
                if (row == null) continue;
                String id = boundedText(stringField(row, "id"), MAX_REMOTE_METADATA_CHARS);
                if (id.isEmpty()) continue;
                MediaMetadata.Builder metadata = new MediaMetadata.Builder()
                        .setTitle(boundedText(stringField(row, "title", "fnAudio"), MAX_REMOTE_METADATA_CHARS))
                        .setArtist(boundedText(stringField(row, "artist"), MAX_REMOTE_METADATA_CHARS))
                        .setAlbumTitle(boundedText(stringField(row, "album"), MAX_REMOTE_METADATA_CHARS));
                long durationMs = boundedLong(longField(row, "durationMs"), 0L, MAX_REMOTE_DURATION_MS);
                if (durationMs > 0L) metadata.setDurationMs(durationMs);
                String artwork = boundedText(stringField(row, "artwork"), MAX_REMOTE_METADATA_CHARS);
                metadata.setArtworkUri(safeRemoteArtworkUri(artwork, fallbackArtwork));
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

    private static String persistedString(JSONObject object, String key, String fallback) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof String ? (String) value : fallback;
    }

    private static boolean booleanField(JSONObject object, String key, boolean fallback) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof Boolean ? (Boolean) value : fallback;
    }

    private static long secondsField(JSONObject object, String key, long fallbackMs) {
        Object value = object == null ? null : object.opt(key);
        if (!(value instanceof Number) || value instanceof Boolean) return fallbackMs;
        double seconds = ((Number) value).doubleValue();
        if (!Double.isFinite(seconds) || seconds < 0d) return fallbackMs;
        double maxSeconds = MAX_REMOTE_DURATION_MS / 1000d;
        if (seconds > maxSeconds) return MAX_REMOTE_DURATION_MS;
        return Math.max(0L, Math.round(seconds * 1000d));
    }

    private static boolean persistedBoolean(JSONObject object, String key, boolean fallback) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof Boolean ? (Boolean) value : fallback;
    }

    private static int persistedInt(JSONObject object, String key, int fallback) {
        Object value = object == null ? null : object.opt(key);
        if (!(value instanceof Number)) return fallback;
        double numeric = ((Number) value).doubleValue();
        if (!Double.isFinite(numeric) || numeric != Math.rint(numeric)
                || numeric < Integer.MIN_VALUE || numeric > Integer.MAX_VALUE) return fallback;
        return (int) numeric;
    }

    private static long persistedLong(JSONObject object, String key, long fallback) {
        Object value = object == null ? null : object.opt(key);
        if (!(value instanceof Number)) return fallback;
        double numeric = ((Number) value).doubleValue();
        if (!Double.isFinite(numeric) || numeric != Math.rint(numeric)
                || numeric < 0d || numeric > Long.MAX_VALUE) return fallback;
        return ((Number) value).longValue();
    }

    private static String boundedText(@Nullable String value, int maxChars) {
        String text = clean(value);
        return text.length() > maxChars ? text.substring(0, maxChars) : text;
    }

    private static String boundedIdentity(@Nullable String value, int maxChars) {
        String text = clean(value);
        return text.length() > maxChars ? "" : text;
    }

    private static long boundedLong(long value, long minimum, long maximum) {
        return Math.max(minimum, Math.min(maximum, value));
    }

    private static String stringField(JSONObject row, String key) {
        return stringField(row, key, "");
    }

    private static String stringField(JSONObject row, String key, String fallback) {
        Object value = row == null ? null : row.opt(key);
        return value instanceof String ? (String) value : fallback;
    }

    private static long longField(JSONObject row, String key) {
        Object value = row == null ? null : row.opt(key);
        if (value instanceof Boolean || !(value instanceof Number) && !(value instanceof String)) return 0L;
        try {
            if (value instanceof Number) {
                double numeric = ((Number) value).doubleValue();
                if (!Double.isFinite(numeric) || numeric < 0d || numeric != Math.rint(numeric)
                        || numeric > Long.MAX_VALUE) return 0L;
                return ((Number) value).longValue();
            }
            String text = ((String) value).trim();
            if (text.isEmpty() || !text.matches("[0-9]+")) return 0L;
            return Long.parseLong(text);
        } catch (RuntimeException ignored) {
            return 0L;
        }
    }

    private static Uri safeRemoteArtworkUri(String value, Uri fallback) {
        if (value.isEmpty()) return fallback;
        try {
            Uri uri = Uri.parse(value);
            String scheme = uri.getScheme();
            boolean http = "http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme);
            int port = uri.getPort();
            return http && uri.getHost() != null && uri.getUserInfo() == null
                    && (port == -1 || (port >= 1 && port <= 65535)) ? uri : fallback;
        } catch (RuntimeException ignored) {
            return fallback;
        }
    }

    private static String repeatName(int mode) {
        if (mode == Player.REPEAT_MODE_ONE) return "one";
        if (mode == Player.REPEAT_MODE_ALL) return "all";
        return "off";
    }

    private static int repeatModeFromName(String name) {
        if ("one".equalsIgnoreCase(name)) return Player.REPEAT_MODE_ONE;
        if ("all".equalsIgnoreCase(name)) return Player.REPEAT_MODE_ALL;
        return Player.REPEAT_MODE_OFF;
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
