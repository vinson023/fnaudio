package com.fnaudio.client.tv;

import android.os.Handler;
import android.os.Looper;

import androidx.annotation.Nullable;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Loads one track's lyrics and keeps the answer states apart.
 *
 * <p>This is the half of the old full-screen lyric page that was worth keeping:
 * the provider queue answers {@code pending} while the lookup is still running,
 * {@code no_match} when it has given up, and {@code failed} when the call itself
 * broke. Each of those needs a different sentence on screen, so they survive as
 * distinct states instead of collapsing into "no lyrics".
 *
 * <p>The other half - how the lines are drawn - now lives in {@link TvLyricColumn}
 * and {@link TvLyricLine}, because the player page shows the same data twice:
 * a single line under the title in cover mode, and the full column in lyric
 * mode. A controller with no views is what makes that possible.
 */
final class TvLyricSource {
    interface Listener {
        /** Lines, the status sentence, or both changed. */
        void onLyricsUpdated();
    }

    /** Same cadence and ceiling as the phone client's lyric poll. */
    private static final long POLL_MS = 1500L;
    private static final int POLL_MAX = 15;

    private final TvApi api;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final List<TvLyricsParser.Line> lines = new ArrayList<>();

    @Nullable private Listener listener;
    @Nullable private TvApi.Track track;
    private String status = "";
    /** Guards against a slow answer landing after the viewer changed track. */
    private int token;
    private int attempts;

    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if (track != null) fetch(track, true);
        }
    };

    TvLyricSource(TvApi api) {
        this.api = api;
    }

    void setListener(@Nullable Listener value) {
        this.listener = value;
    }

    /**
     * Drops whatever was on screen and starts a lookup for {@code track}.
     *
     * <p>Always clears first: keeping the previous song's lines visible for the
     * second the request takes reads as "this song has the wrong lyrics".
     */
    void load(@Nullable TvApi.Track value) {
        token++;
        main.removeCallbacks(poll);
        lines.clear();
        attempts = 0;
        track = value;
        if (value == null) {
            status = "";
            notifyListener();
            return;
        }
        status = "正在匹配歌词…";
        notifyListener();
        fetch(value, false);
    }

    /** Timed or untimed lines; empty while a lookup is in flight. */
    List<TvLyricsParser.Line> lines() {
        return Collections.unmodifiableList(lines);
    }

    /** Sentence to show instead of lines; empty when there are lines. */
    String status() {
        return status;
    }

    boolean hasTiming() {
        return TvLyricsParser.hasTiming(lines);
    }

    /** Index of the line to light at {@code positionMs}, or -1. */
    int indexAt(long positionMs) {
        return TvLyricsParser.indexAt(lines, positionMs);
    }

    void release() {
        token++;
        main.removeCallbacks(poll);
        io.shutdownNow();
    }

    private void fetch(final TvApi.Track value, final boolean retry) {
        final int requestToken = ++token;
        io.execute(new Runnable() {
            @Override public void run() {
                TvApi.Lyrics answer = null;
                String failure = "";
                try {
                    answer = api.lyrics(value.id, retry);
                } catch (IOException error) {
                    failure = describe(error);
                }
                final TvApi.Lyrics result = answer;
                final String failureText = failure;
                main.post(new Runnable() {
                    @Override public void run() {
                        if (requestToken != token || track != value) return;
                        apply(result, failureText);
                    }
                });
            }
        });
    }

    private void apply(@Nullable TvApi.Lyrics answer, String failure) {
        if (answer == null) {
            status = failure.isEmpty() ? "歌词加载失败" : failure;
            notifyListener();
            return;
        }
        if (answer.pending) {
            schedulePoll();
            return;
        }
        if (!answer.text.isEmpty()) {
            List<TvLyricsParser.Line> rows = TvLyricsParser.parse(answer.text);
            if (!rows.isEmpty()) {
                lines.clear();
                lines.addAll(rows);
                status = "";
                notifyListener();
                return;
            }
        }
        if ("no_match".equals(answer.status)) {
            status = "这首歌没有歌词";
        } else if ("failed".equals(answer.status)) {
            status = answer.error.isEmpty() ? "歌词获取失败" : "歌词获取失败\n" + answer.error;
        } else {
            status = "这首歌暂时没有歌词";
        }
        notifyListener();
    }

    private void schedulePoll() {
        if (attempts >= POLL_MAX) {
            status = "歌词还在匹配中\n稍后重新打开播放页查看";
            notifyListener();
            return;
        }
        attempts++;
        status = "正在匹配歌词…";
        notifyListener();
        main.postDelayed(poll, POLL_MS);
    }

    private void notifyListener() {
        if (listener != null) listener.onLyricsUpdated();
    }

    private static String describe(IOException error) {
        if (error instanceof TvApi.TvAuthException) {
            return "登录已过期\n请回连接页重新连接";
        }
        String detail = error.getMessage() == null ? "" : error.getMessage().trim();
        if (detail.isEmpty()) return "歌词加载失败";
        return "歌词加载失败\n" + detail;
    }
}
