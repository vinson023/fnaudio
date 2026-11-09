package com.fnaudio.client.tv;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import androidx.annotation.Nullable;
import androidx.media3.common.MediaItem;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.datasource.DataSource;
import androidx.media3.datasource.DefaultDataSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Local playback for the television client.
 *
 * <p>The phone app hands playback to a MediaSessionService so the music keeps
 * running while the WebView is in the background. A TV client never leaves the
 * foreground, so it owns one {@link ExoPlayer} directly. That removes the
 * controller handshake, the notification, and the session token dance from the
 * critical path while keeping the same server-side stream endpoint.
 *
 * <p>Queue semantics deliberately mirror the WebView: the queue is an ordered
 * list plus a cursor, "next" advances the cursor, and the end of the list either
 * stops or wraps depending on {@link #setRepeatAll(boolean)}. Shuffle picks a
 * random index other than the current one on every advance, exactly like
 * {@code PlaybackCore.next_track()}, rather than pre-shuffling the list.
 */
public final class TvPlayer {
    public interface Listener {
        void onTrackChanged(@Nullable TvApi.Track track, int index);
        void onPlayingChanged(boolean playing);
        void onProgress(long positionMs, long durationMs);
        void onQueueChanged();
    }

    private static final long TICK_MS = 500L;

    private final Context context;
    private final TvApi api;
    private final ExoPlayer player;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<TvApi.Track> queue = new ArrayList<>();

    @Nullable private Listener listener;
    private int cursor = -1;
    private boolean repeatAll;
    private boolean shuffle;
    private boolean ticking;
    private final java.util.Random random = new java.util.Random();

    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (listener != null) {
                listener.onProgress(player.getCurrentPosition(), player.getDuration());
            }
            if (ticking) handler.postDelayed(this, TICK_MS);
        }
    };

    public TvPlayer(Context context, TvApi api) {
        this.context = context.getApplicationContext();
        this.api = api;
        this.player = buildPlayer();
        player.addListener(new Player.Listener() {
            @Override public void onIsPlayingChanged(boolean isPlaying) {
                if (listener != null) listener.onPlayingChanged(isPlaying);
                setTicking(isPlaying);
            }

            @Override public void onPlaybackStateChanged(int state) {
                if (state == Player.STATE_ENDED) advance(true);
                if (state == Player.STATE_READY && listener != null) {
                    listener.onProgress(player.getCurrentPosition(), player.getDuration());
                }
            }

            @Override public void onPlayerError(PlaybackException error) {
                // A dead track must not freeze the queue: the television has no
                // visible error surface beyond the row, so skip and stay alive.
                advance(true);
            }
        });
    }

    private ExoPlayer buildPlayer() {
        // The stream route sits behind the same authenticated CGI path as the
        // library, so every media request carries the profile's bearer token.
        Map<String, String> headers = new HashMap<>();
        if (!api.profile().webSession) {
            headers.put("Authorization", "Bearer " + api.profile().token);
            headers.put("X-Fnaudio-Trim-Token", api.profile().token);
            headers.put("Cookie", api.cookieHeader());
        }
        DefaultHttpDataSource.Factory http = new DefaultHttpDataSource.Factory()
                .setDefaultRequestProperties(headers)
                .setAllowCrossProtocolRedirects(true)
                .setConnectTimeoutMs(15000)
                .setReadTimeoutMs(30000);
        DataSource.Factory dataSource = new DefaultDataSource.Factory(context, http);
        return new ExoPlayer.Builder(context)
                .setMediaSourceFactory(new DefaultMediaSourceFactory(dataSource))
                .setHandleAudioBecomingNoisy(true)
                .build();
    }

    public void setListener(@Nullable Listener value) {
        this.listener = value;
    }

    public List<TvApi.Track> queue() {
        return Collections.unmodifiableList(queue);
    }

    public int cursor() {
        return cursor;
    }

    @Nullable
    public TvApi.Track current() {
        return cursor >= 0 && cursor < queue.size() ? queue.get(cursor) : null;
    }

    public boolean isPlaying() {
        return player.isPlaying();
    }

    /** Replaces the queue and starts at {@code startIndex}. */
    public void play(List<TvApi.Track> tracks, int startIndex) {
        if (tracks == null || tracks.isEmpty()) return;
        int start = Math.max(0, Math.min(tracks.size() - 1, startIndex));
        queue.clear();
        queue.addAll(tracks);
        cursor = start;
        loadCurrent(true);
        if (listener != null) listener.onQueueChanged();
    }

    /** Appends to the queue without interrupting playback. */
    public void enqueue(TvApi.Track track) {
        if (track == null) return;
        for (TvApi.Track existing : queue) {
            if (existing.id.equals(track.id)) return;
        }
        queue.add(track);
        if (cursor < 0) {
            cursor = 0;
            loadCurrent(true);
        }
        if (listener != null) listener.onQueueChanged();
    }

    public void toggle() {
        if (current() == null) {
            if (!queue.isEmpty()) {
                cursor = 0;
                loadCurrent(true);
            }
            return;
        }
        if (player.isPlaying()) player.pause(); else player.play();
    }

    public void next() {
        advance(false);
    }

    public void previous() {
        if (queue.isEmpty()) return;
        if (player.getCurrentPosition() > 5000) {
            player.seekTo(0);
            return;
        }
        if (cursor <= 0) {
            if (!repeatAll) {
                player.seekTo(0);
                return;
            }
            cursor = queue.size() - 1;
        } else {
            cursor--;
        }
        loadCurrent(true);
    }

    public void seekTo(long positionMs) {
        player.seekTo(Math.max(0, positionMs));
    }

    /** Current position in the loaded item; 0 when nothing is prepared. */
    public long position() {
        return Math.max(0, player.getCurrentPosition());
    }

    /** Loaded item length, or -1 while the player has no timeline yet. */
    public long duration() {
        return player.getDuration();
    }

    public void playAt(int index) {
        if (index < 0 || index >= queue.size()) return;
        cursor = index;
        loadCurrent(true);
    }

    public void setRepeatAll(boolean enabled) {
        repeatAll = enabled;
    }

    public boolean repeatAll() {
        return repeatAll;
    }

    public void setShuffle(boolean enabled) {
        shuffle = enabled;
    }

    public boolean shuffle() {
        return shuffle;
    }

    public void release() {
        setTicking(false);
        player.release();
    }

    private void advance(boolean auto) {
        if (queue.isEmpty()) return;
        if (shuffle && queue.size() > 1) {
            int next = cursor;
            while (next == cursor) next = random.nextInt(queue.size());
            cursor = next;
            loadCurrent(auto);
            return;
        }
        if (cursor + 1 < queue.size()) {
            cursor++;
        } else if (repeatAll) {
            cursor = 0;
        } else {
            player.pause();
            if (!auto) player.seekTo(0);
            if (listener != null) listener.onPlayingChanged(false);
            return;
        }
        loadCurrent(auto);
    }

    private void loadCurrent(boolean playNow) {
        TvApi.Track track = current();
        if (track == null) return;
        MediaItem item = new MediaItem.Builder()
                .setUri(api.mediaUrl(track))
                .setMediaId(track.id)
                .build();
        player.setMediaItem(item);
        player.prepare();
        if (playNow) player.play();
        if (listener != null) {
            listener.onTrackChanged(track, cursor);
            listener.onProgress(0, track.durationMs);
        }
    }

    private void setTicking(boolean on) {
        if (on == ticking) return;
        ticking = on;
        handler.removeCallbacks(tick);
        if (on) handler.post(tick);
    }
}
