package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.Nullable;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Full-screen lyrics page that sits on top of the now-playing surface.
 *
 * <p>A television has no room for a side panel here: lyric lines need to be
 * readable from three metres, so the whole screen is given over to them, with
 * the current line larger and lit while the rest stay dim. The page follows
 * playback — {@link #onProgress(long)} comes from the player tick — and keeps
 * the active line vertically centred by scrolling, which is the one piece of
 * motion a viewer expects from a lyric screen.
 *
 * <p>Lookup state is modelled after the phone client: {@code pending} means the
 * provider queue has not answered yet and the page retries a bounded number of
 * times, while {@code no_match} is a terminal answer that only an explicit
 * reopen will re-query.
 */
final class TvLyricsView extends FrameLayout {
    interface OnClose {
        void onClose();
    }

    /** Same cadence and ceiling as the phone client's lyric poll. */
    private static final long POLL_MS = 1500L;
    private static final int POLL_MAX = 15;
    private static final float LINE_SP = 21f;
    private static final float ACTIVE_SP = 26f;

    private final TvApi api;
    private final TvArtworkLoader artwork;
    private final ImageView backdrop;
    private final TextView title;
    private final TextView subtitle;
    private final TextView message;
    private final ScrollView scroller;
    private final LinearLayout lines;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<TvLyricsParser.Line> parsed = new ArrayList<>();

    @Nullable private TvApi.Track pendingTrack;
    @Nullable private OnClose onClose;
    /** Guards against a slow answer landing after the viewer changed track. */
    private int requestToken;
    private int pollAttempts;
    private int activeIndex = -1;
    private long lastPositionMs;

    private final Runnable poll = new Runnable() {
        @Override public void run() {
            TvApi.Track track = pendingTrack;
            if (track == null || getVisibility() != VISIBLE) return;
            load(track, false);
        }
    };

    TvLyricsView(Context context, TvApi api, TvArtworkLoader artwork) {
        super(context);
        this.api = api;
        this.artwork = artwork;
        setBackgroundColor(TvUi.BG);

        backdrop = new ImageView(context);
        backdrop.setScaleType(ImageView.ScaleType.CENTER_CROP);
        // Faint: the cover is only there to tint the room, and at full lyric
        // brightness a stronger wash made the empty state look like a smudge.
        backdrop.setAlpha(0.16f);
        addView(backdrop, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        GradientDrawable veil = new GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0xF207080A, 0xE607080A, 0xFA07080A});
        View shade = new View(context);
        shade.setBackground(veil);
        addView(shade, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout content = new LinearLayout(context);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(TvUi.dp(context, 72), TvUi.dp(context, 34),
                TvUi.dp(context, 72), TvUi.dp(context, 26));
        addView(content, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout header = new LinearLayout(context);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        content.addView(header, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        title = new TextView(context);
        title.setTextColor(TvUi.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24f);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setSingleLine(true);
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        header.addView(title, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView hint = new TextView(context);
        hint.setText("返回键回到播放页");
        hint.setTextColor(TvUi.TEXT_3);
        hint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f);
        header.addView(hint);

        subtitle = new TextView(context);
        subtitle.setTextColor(TvUi.TEXT_3);
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(android.text.TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        subtitleParams.topMargin = TvUi.dp(context, 4);
        content.addView(subtitle, subtitleParams);

        FrameLayout stage = new FrameLayout(context);
        LinearLayout.LayoutParams stageParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        stageParams.topMargin = TvUi.dp(context, 10);
        content.addView(stage, stageParams);

        scroller = new ScrollView(context);
        // The scrollbar of a lyric page is noise: the motion itself is the cue.
        scroller.setVerticalScrollBarEnabled(false);
        scroller.setFocusable(false);
        stage.addView(scroller, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        lines = new LinearLayout(context);
        lines.setOrientation(LinearLayout.VERTICAL);
        // Half-screen of slack at both ends so the first and last line can still
        // sit in the middle of the screen instead of hugging an edge.
        lines.setPadding(0, TvUi.dp(context, 150), 0, TvUi.dp(context, 170));
        scroller.addView(lines, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        message = new TextView(context);
        message.setTextColor(TvUi.TEXT_2);
        message.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f);
        message.setGravity(Gravity.CENTER);
        message.setLineSpacing(TvUi.dp(context, 8), 1f);
        message.setVisibility(GONE);
        stage.addView(message, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        setVisibility(GONE);
    }

    void setOnClose(OnClose action) {
        this.onClose = action;
    }

    /** Opens the page for {@code track} at {@code positionMs} and starts the lookup. */
    void show(TvApi.Track track, long positionMs) {
        pendingTrack = track;
        pollAttempts = 0;
        activeIndex = -1;
        // Seeded with the real position so the first painted frame already
        // holds the right line instead of waiting up to one tick for the player.
        lastPositionMs = Math.max(0, positionMs);
        title.setText(track.title);
        subtitle.setText(track.artist + (track.album.isEmpty() ? "" : " · " + track.album));
        artwork.loadHires(track.coverKey, backdrop);
        setVisibility(VISIBLE);
        load(track, false);
    }

    void hide() {
        // Bumping the token retires any answer still in flight, so a late
        // response cannot repaint a page the viewer already left.
        requestToken++;
        handler.removeCallbacks(poll);
        setVisibility(GONE);
    }

    void release() {
        requestToken++;
        handler.removeCallbacks(poll);
        io.shutdownNow();
    }

    /** Player tick; drives the highlight and the scroll. */
    void onProgress(long positionMs) {
        if (getVisibility() != VISIBLE) return;
        lastPositionMs = positionMs;
        if (parsed.isEmpty() || !TvLyricsParser.hasTiming(parsed)) return;
        int index = TvLyricsParser.indexAt(parsed, positionMs);
        if (index == activeIndex) return;
        int previous = activeIndex;
        activeIndex = index;
        if (previous >= 0) styleLine(previous, false);
        if (index >= 0) {
            styleLine(index, true);
            centerOn(index);
        }
    }

    /** Back leaves the lyric page; transport keys stay with the player. */
    boolean handleKey(int keyCode, KeyEvent event) {
        if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            hide();
            if (onClose != null) onClose.onClose();
            return true;
        }
        return false;
    }

    private void load(final TvApi.Track track, final boolean retry) {
        final int token = ++requestToken;
        if (parsed.isEmpty()) showMessage("正在匹配歌词…");
        io.execute(new Runnable() {
            @Override public void run() {
                TvApi.Lyrics answer = null;
                String failure = "";
                try {
                    answer = api.lyrics(track.id, retry);
                } catch (IOException error) {
                    failure = describe(error);
                }
                final TvApi.Lyrics result = answer;
                final String failureText = failure;
                handler.post(new Runnable() {
                    @Override public void run() {
                        if (token != requestToken || getVisibility() != VISIBLE) return;
                        apply(track, result, failureText);
                    }
                });
            }
        });
    }

    private void apply(TvApi.Track track, @Nullable TvApi.Lyrics answer, String failure) {
        if (answer == null) {
            showMessage(failure.isEmpty() ? "歌词加载失败" : failure);
            return;
        }
        if (answer.pending) {
            schedulePoll(track);
            return;
        }
        if (!answer.text.isEmpty()) {
            List<TvLyricsParser.Line> rows = TvLyricsParser.parse(answer.text);
            if (!rows.isEmpty()) {
                render(rows);
                return;
            }
        }
        if ("no_match".equals(answer.status)) {
            showMessage("暂未找到歌词\n重新打开歌词页可以再查一次");
        } else if ("failed".equals(answer.status)) {
            showMessage(answer.error.isEmpty()
                    ? "歌词获取失败"
                    : "歌词获取失败\n" + answer.error);
        } else {
            showMessage("这首歌暂时没有歌词");
        }
    }

    private void schedulePoll(TvApi.Track track) {
        if (pollAttempts >= POLL_MAX) {
            showMessage("歌词还在匹配中\n稍后重新打开歌词页查看");
            return;
        }
        pollAttempts++;
        showMessage("正在获取歌词…");
        handler.postDelayed(poll, POLL_MS);
    }

    private void render(List<TvLyricsParser.Line> rows) {
        parsed.clear();
        parsed.addAll(rows);
        activeIndex = -1;
        message.setVisibility(GONE);
        scroller.setVisibility(VISIBLE);
        lines.removeAllViews();
        for (int index = 0; index < rows.size(); index++) {
            lines.addView(lineView(rows.get(index).text));
        }
        if (TvLyricsParser.hasTiming(parsed)) {
            // Re-entering the page mid-song must land on the right line at once
            // instead of waiting for the next tick.
            onProgress(lastPositionMs);
            if (activeIndex < 0) scroller.scrollTo(0, 0);
        } else {
            scroller.scrollTo(0, 0);
        }
    }

    private void showMessage(String text) {
        parsed.clear();
        activeIndex = -1;
        lines.removeAllViews();
        scroller.setVisibility(GONE);
        scroller.scrollTo(0, 0);
        message.setText(text);
        message.setVisibility(VISIBLE);
    }

    private TextView lineView(String text) {
        TextView view = new TextView(getContext());
        view.setText(text);
        view.setTextColor(TvUi.TEXT_3);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, LINE_SP);
        view.setGravity(Gravity.CENTER_HORIZONTAL);
        view.setLineSpacing(TvUi.dp(getContext(), 4), 1f);
        view.setPadding(TvUi.dp(getContext(), 12), TvUi.dp(getContext(), 9),
                TvUi.dp(getContext(), 12), TvUi.dp(getContext(), 9));
        view.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return view;
    }

    private void styleLine(int index, boolean active) {
        if (index < 0 || index >= lines.getChildCount()) return;
        View child = lines.getChildAt(index);
        if (!(child instanceof TextView)) return;
        TextView view = (TextView) child;
        view.setTextColor(active ? TvUi.TEXT : TvUi.TEXT_3);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, active ? ACTIVE_SP : LINE_SP);
        view.setTypeface(active ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
    }

    private void centerOn(final int index) {
        // Two frames of slack: the active line grew by 5sp, so the new geometry
        // only exists after this pass has been laid out.
        lines.post(new Runnable() {
            @Override public void run() {
                if (index >= lines.getChildCount()) return;
                View line = lines.getChildAt(index);
                int target = line.getTop() + line.getHeight() / 2 - scroller.getHeight() / 2;
                scroller.smoothScrollTo(0, Math.max(0, target));
            }
        });
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
