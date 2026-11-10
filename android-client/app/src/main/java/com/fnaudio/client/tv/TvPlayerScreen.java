package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;

import java.util.Collections;
import java.util.List;

/**
 * The now-playing page, in the two forms both reference clients converged on.
 *
 * <p><b>Cover mode</b> (default): information on the left, a 56.2%-of-height
 * square cover on the right, one lyric line under the artist.
 * <b>Lyric mode</b>: the cover shrinks to 29.6% and moves left, and the lyric
 * column takes the right 42.7% x 56.2% box. The two boxes share one grid, so
 * switching forms only trades width between the cover and the words instead of
 * relaying the screen out.
 *
 * <p>Numbers come from {@code activity_player.xml} and
 * {@code activity_player_style_lyric.xml} in {@code references/TVapp/}, where
 * the same screen is expressed as percentage guidelines. They are recomputed in
 * {@link #onSizeChanged} rather than baked in dp, so a 720p set and a 4K set get
 * the same composition.
 *
 * <p>The control bar keeps its buttons on screen instead of hiding them: our
 * library is local and small, so picking and skipping is the main activity,
 * unlike a streaming service where the page is mostly something to look at.
 */
final class TvPlayerScreen extends FrameLayout {
    interface OnClose {
        void onClose();
    }

    private static final int MODE_COVER = 0;
    private static final int MODE_LYRIC = 1;

    private static final float EDGE_DP = 70f;
    private static final float COVER_RATIO = 0.562f;
    private static final float SMALL_COVER_RATIO = 0.296f;
    private static final float LYRIC_WIDTH_RATIO = 0.427f;
    private static final float LYRIC_HEIGHT_RATIO = 0.562f;
    private static final float LEFT_COLUMN_RATIO = 0.453f;
    /** 21.6% of 540dp, rounded: a fixed height needs no second layout pass. */
    private static final float BAR_H_DP = 117f;
    private static final long SEEK_STEP_MS = 10000L;

    private final TvPlayer player;
    private final TvArtworkLoader artwork;
    private final TvLyricSource lyrics;

    private final ImageView backdrop;
    private final FrameLayout body;
    private final FrameLayout coverStage;
    private final LinearLayout lyricStage;

    private final TextView title;
    private final TextView subtitle;
    private final TvLyricLine singleLine;

    private final FrameLayout bigCoverBox;
    private final ImageView bigCover;
    private final FrameLayout smallCoverBox;
    private final ImageView smallCover;
    private final TextView smallTitle;
    private final TextView smallSubtitle;
    private final TvLyricColumn lyricColumn;

    private final LinearLayout controlBar;
    private final TvSeekStrip seek;
    private final TextView elapsed;
    private final TextView total;
    private final TextView backButton;
    private final TextView playButton;
    private final TextView lyricsButton;
    private final TvQueueSheet queueSheet;

    @Nullable private OnClose closeListener;
    private List<TvLyricsParser.Line> currentLines = Collections.emptyList();
    private int mode = MODE_COVER;
    private int activeIndex = -1;
    private long durationMs;

    TvPlayerScreen(Context context, TvPlayer player, TvApi api, TvArtworkLoader artwork) {
        super(context);
        this.player = player;
        this.artwork = artwork;
        this.lyrics = new TvLyricSource(api);
        lyrics.setListener(this::onLyricsUpdated);

        setBackgroundColor(TvTheme.BG);
        setFocusable(false);

        backdrop = new ImageView(context);
        backdrop.setScaleType(ImageView.ScaleType.CENTER_CROP);
        backdrop.setAlpha(0.30f);
        addView(backdrop, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        GradientDrawable veil = new GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{0xF2080812, 0xE6080812, 0xFA080812});
        View shade = new View(context);
        shade.setBackground(veil);
        addView(shade, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        body = new FrameLayout(context);
        FrameLayout.LayoutParams bodyParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        bodyParams.bottomMargin = TvTheme.dp(context, BAR_H_DP);
        addView(body, bodyParams);

        // ---------------------------------------------------------- 封面形态
        coverStage = new FrameLayout(context);
        body.addView(coverStage, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout left = new LinearLayout(context);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setGravity(Gravity.CENTER_VERTICAL);
        left.setPadding(TvTheme.dp(context, EDGE_DP), 0, 0, 0);
        FrameLayout.LayoutParams leftParams = new FrameLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, Gravity.START);
        coverStage.addView(left, leftParams);

        title = new TextView(context);
        title.setTextColor(TvTheme.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.PLAYER_TITLE);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.MARQUEE);
        title.setSelected(true);
        left.addView(title);

        subtitle = new TextView(context);
        subtitle.setTextColor(TvTheme.TEXT_3);
        subtitle.setTextSize(TvTheme.PLAYER_SUB);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        subtitleParams.topMargin = TvTheme.dp(context, 6);
        left.addView(subtitle, subtitleParams);

        singleLine = new TvLyricLine(context);
        LinearLayout.LayoutParams lineParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lineParams.topMargin = TvTheme.dp(context, 22);
        left.addView(singleLine, lineParams);

        bigCoverBox = new FrameLayout(context);
        bigCoverBox.setBackground(TvTheme.rounded(context, 0xFF14161F, 10f));
        TvUi.roundClip(bigCoverBox, 10f);
        FrameLayout.LayoutParams bigParams = new FrameLayout.LayoutParams(
                0, 0, Gravity.END | Gravity.CENTER_VERTICAL);
        bigParams.rightMargin = TvTheme.dp(context, EDGE_DP);
        coverStage.addView(bigCoverBox, bigParams);

        bigCover = new ImageView(context);
        bigCover.setScaleType(ImageView.ScaleType.CENTER_CROP);
        bigCoverBox.addView(bigCover, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // ---------------------------------------------------------- 歌词形态
        lyricStage = new LinearLayout(context);
        lyricStage.setOrientation(LinearLayout.HORIZONTAL);
        lyricStage.setGravity(Gravity.CENTER_VERTICAL);
        lyricStage.setPadding(TvTheme.dp(context, EDGE_DP), 0, 0, 0);
        lyricStage.setVisibility(GONE);
        body.addView(lyricStage, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout lyricLeft = new LinearLayout(context);
        lyricLeft.setOrientation(LinearLayout.VERTICAL);
        lyricLeft.setGravity(Gravity.CENTER_VERTICAL);
        lyricStage.addView(lyricLeft, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT));

        smallCoverBox = new FrameLayout(context);
        smallCoverBox.setBackground(TvTheme.rounded(context, 0xFF14161F, 8f));
        TvUi.roundClip(smallCoverBox, 8f);
        lyricLeft.addView(smallCoverBox, new LinearLayout.LayoutParams(0, 0));

        smallCover = new ImageView(context);
        smallCover.setScaleType(ImageView.ScaleType.CENTER_CROP);
        smallCoverBox.addView(smallCover, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        smallTitle = new TextView(context);
        smallTitle.setTextColor(TvTheme.TEXT);
        smallTitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.PLAYER_TITLE);
        smallTitle.setTypeface(Typeface.DEFAULT_BOLD);
        smallTitle.setSingleLine(true);
        smallTitle.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams smallTitleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        smallTitleParams.topMargin = TvTheme.dp(context, 14);
        lyricLeft.addView(smallTitle, smallTitleParams);

        smallSubtitle = new TextView(context);
        smallSubtitle.setTextColor(TvTheme.TEXT_3);
        smallSubtitle.setTextSize(TvTheme.PLAYER_SUB);
        smallSubtitle.setSingleLine(true);
        smallSubtitle.setEllipsize(TextUtils.TruncateAt.END);
        lyricLeft.addView(smallSubtitle);

        lyricColumn = new TvLyricColumn(context);
        LinearLayout.LayoutParams columnParams = new LinearLayout.LayoutParams(0, 0);
        columnParams.leftMargin = TvTheme.dp(context, 12);
        lyricStage.addView(lyricColumn, columnParams);

        // ---------------------------------------------------------- 控制条
        controlBar = new LinearLayout(context);
        controlBar.setOrientation(LinearLayout.VERTICAL);
        controlBar.setBackgroundColor(TvTheme.BG_ELEVATED);
        FrameLayout.LayoutParams barParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                TvTheme.dp(context, BAR_H_DP), Gravity.BOTTOM);
        addView(controlBar, barParams);

        LinearLayout seekRow = new LinearLayout(context);
        seekRow.setOrientation(LinearLayout.HORIZONTAL);
        seekRow.setGravity(Gravity.CENTER_VERTICAL);
        seekRow.setPadding(TvTheme.dp(context, EDGE_DP), 0, TvTheme.dp(context, EDGE_DP), 0);
        controlBar.addView(seekRow, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 0.42f));

        elapsed = timeLabel(context);
        seekRow.addView(elapsed);

        seek = new TvSeekStrip(context);
        seek.setOnSeek(direction -> player.seekTo(Math.max(0, player.position()
                + direction * SEEK_STEP_MS)));
        LinearLayout.LayoutParams seekParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
        seekParams.leftMargin = TvTheme.dp(context, 10);
        seekParams.rightMargin = TvTheme.dp(context, 10);
        seekRow.addView(seek, seekParams);

        total = timeLabel(context);
        seekRow.addView(total);

        LinearLayout buttons = new LinearLayout(context);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        buttons.setGravity(Gravity.CENTER_VERTICAL);
        buttons.setPadding(TvTheme.dp(context, EDGE_DP), 0, TvTheme.dp(context, EDGE_DP), 0);
        controlBar.addView(buttons, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 0.58f));

        backButton = pillButton(context, "返回");
        backButton.setOnClickListener(view -> close());
        FrameLayout.LayoutParams backParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        backParams.leftMargin = TvTheme.dp(context, EDGE_DP);
        backParams.topMargin = TvTheme.dp(context, 30);
        backParams.gravity = Gravity.START | Gravity.TOP;
        addView(backButton, backParams);

        TextView previous = pillButton(context, "上一首");
        previous.setOnClickListener(view -> player.previous());
        buttons.addView(previous);

        playButton = pillButton(context, "播放");
        playButton.setOnClickListener(view -> player.toggle());
        buttons.addView(playButton, gap(context, 10));

        TextView next = pillButton(context, "下一首");
        next.setOnClickListener(view -> player.next());
        buttons.addView(next);

        TextView shuffle = pillButton(context, "随机");
        shuffle.setOnClickListener(view -> {
            player.setShuffle(!player.shuffle());
            shuffle.setText(player.shuffle() ? "随机 · 开" : "随机");
            shuffle.setTextColor(player.shuffle() ? TvTheme.ACCENT : TvTheme.TEXT);
        });
        buttons.addView(shuffle, gap(context, 22));

        TextView repeat = pillButton(context, "循环");
        repeat.setOnClickListener(view -> {
            player.setRepeatAll(!player.repeatAll());
            repeat.setText(player.repeatAll() ? "循环 · 开" : "循环");
            repeat.setTextColor(player.repeatAll() ? TvTheme.ACCENT : TvTheme.TEXT);
        });
        buttons.addView(repeat, gap(context, 8));

        lyricsButton = pillButton(context, "歌词");
        lyricsButton.setOnClickListener(view -> setMode(mode == MODE_COVER ? MODE_LYRIC : MODE_COVER));
        buttons.addView(lyricsButton, gap(context, 22));

        TextView queueButton = pillButton(context, "队列");
        queueButton.setOnClickListener(view -> openQueue());
        buttons.addView(queueButton, gap(context, 8));

        // Explicit next-focus ids: with pills of uneven width the geometric
        // search skips over the narrow ones, which is how the previous player
        // made its last button unreachable.
        backButton.setNextFocusDownId(seek.getId());
        seek.setNextFocusUpId(backButton.getId());
        seek.setNextFocusDownId(playButton.getId());
        previous.setNextFocusUpId(seek.getId());
        playButton.setNextFocusUpId(seek.getId());
        next.setNextFocusUpId(seek.getId());
        shuffle.setNextFocusUpId(seek.getId());
        repeat.setNextFocusUpId(seek.getId());
        lyricsButton.setNextFocusUpId(seek.getId());
        queueButton.setNextFocusUpId(seek.getId());
        previous.setNextFocusRightId(playButton.getId());
        playButton.setNextFocusLeftId(previous.getId());
        playButton.setNextFocusRightId(next.getId());
        next.setNextFocusLeftId(playButton.getId());
        next.setNextFocusRightId(shuffle.getId());
        shuffle.setNextFocusLeftId(next.getId());
        shuffle.setNextFocusRightId(repeat.getId());
        repeat.setNextFocusLeftId(shuffle.getId());
        repeat.setNextFocusRightId(lyricsButton.getId());
        lyricsButton.setNextFocusLeftId(repeat.getId());
        lyricsButton.setNextFocusRightId(queueButton.getId());
        queueButton.setNextFocusLeftId(lyricsButton.getId());

        queueSheet = new TvQueueSheet(context);
        queueSheet.setOnPick(position -> {
            player.playAt(position);
            queueSheet.close();
            playButton.requestFocus();
        });
        queueSheet.setOnClose(playButton::requestFocus);
        addView(queueSheet, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        setVisibility(GONE);
    }

    private static LinearLayout.LayoutParams gap(Context context, int dp) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.leftMargin = TvTheme.dp(context, dp);
        return params;
    }

    private TextView timeLabel(Context context) {
        TextView label = new TextView(context);
        label.setText("0:00");
        label.setTextColor(TvTheme.TEXT_4);
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        label.setTypeface(Typeface.MONOSPACE);
        label.setMinWidth(TvTheme.dp(context, 48));
        return label;
    }

    private TextView pillButton(Context context, String text) {
        TextView button = new TextView(context);
        button.setText(text);
        button.setId(View.generateViewId());
        button.setTextColor(TvTheme.TEXT);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_SUB);
        button.setGravity(Gravity.CENTER);
        button.setSingleLine(true);
        button.setFocusable(true);
        button.setFocusableInTouchMode(false);
        button.setPadding(TvTheme.dp(context, 16), TvTheme.dp(context, 9),
                TvTheme.dp(context, 16), TvTheme.dp(context, 9));
        button.setBackground(TvTheme.cardBackground(context, TvTheme.R_PILL));
        button.setForeground(TvTheme.focusRing(context, TvTheme.R_PILL));
        button.setOnFocusChangeListener((view, hasFocus) -> view.animate()
                .scaleX(hasFocus ? 1.05f : 1f).scaleY(hasFocus ? 1.05f : 1f)
                .setDuration(TvTheme.FOCUS_MS).start());
        return button;
    }

    // ------------------------------------------------------------- 尺寸换算

    @Override
    protected void onSizeChanged(int width, int height, int oldWidth, int oldHeight) {
        super.onSizeChanged(width, height, oldWidth, oldHeight);
        int edge = TvTheme.dp(getContext(), EDGE_DP);
        int cover = Math.round(height * COVER_RATIO);
        FrameLayout.LayoutParams bigParams =
                (FrameLayout.LayoutParams) bigCoverBox.getLayoutParams();
        bigParams.width = cover;
        bigParams.height = cover;
        bigCoverBox.setLayoutParams(bigParams);

        // Left column stops where the cover starts, so a long title cannot run
        // underneath the artwork on a narrow panel.
        View left = coverStage.getChildAt(0);
        FrameLayout.LayoutParams leftParams = (FrameLayout.LayoutParams) left.getLayoutParams();
        leftParams.width = Math.max(0, Math.round(width * 0.55f) - edge);
        left.setLayoutParams(leftParams);

        int small = Math.round(height * SMALL_COVER_RATIO);
        LinearLayout.LayoutParams smallParams =
                (LinearLayout.LayoutParams) smallCoverBox.getLayoutParams();
        smallParams.width = small;
        smallParams.height = small;
        smallCoverBox.setLayoutParams(smallParams);

        View lyricLeft = lyricStage.getChildAt(0);
        LinearLayout.LayoutParams lyricLeftParams =
                (LinearLayout.LayoutParams) lyricLeft.getLayoutParams();
        lyricLeftParams.width = Math.max(0, Math.round(width * LEFT_COLUMN_RATIO) - edge);
        lyricLeft.setLayoutParams(lyricLeftParams);

        LinearLayout.LayoutParams columnParams =
                (LinearLayout.LayoutParams) lyricColumn.getLayoutParams();
        columnParams.width = Math.round(width * LYRIC_WIDTH_RATIO);
        columnParams.height = Math.round(height * LYRIC_HEIGHT_RATIO);
        lyricColumn.setLayoutParams(columnParams);
    }

    // ------------------------------------------------------------- 生命周期

    void setOnClose(OnClose value) {
        this.closeListener = value;
    }

    /** Opens the page for whatever is playing; callers ensure a track exists. */
    void open() {
        TvApi.Track track = player.current();
        if (track == null) return;
        setMode(MODE_COVER);
        bind(track);
        setVisibility(VISIBLE);
        // Deferred one frame: the page was GONE, so nothing is laid out yet and
        // an immediate request lands on a child with zero size.
        focusPlayWhenLaidOut();
    }

    /**
     * Requests the highlight once the page has been measured.
     *
     * <p>A plain {@code post} is not enough: the page was {@code GONE}, so the
     * first message can run before the layout that gives the buttons a size,
     * and {@code requestFocus} on a zero-height view quietly returns false -
     * which is exactly how this page opened with no highlight at all.
     */
    private void focusPlayWhenLaidOut() {
        playButton.getViewTreeObserver().addOnGlobalLayoutListener(
                new ViewTreeObserver.OnGlobalLayoutListener() {
                    @Override public void onGlobalLayout() {
                        ViewTreeObserver observer = playButton.getViewTreeObserver();
                        if (observer.isAlive()) observer.removeOnGlobalLayoutListener(this);
                        if (isOpen()) playButton.requestFocus();
                    }
                });
    }

    void close() {
        queueSheet.close();
        lyrics.load(null);
        setVisibility(GONE);
        if (closeListener != null) closeListener.onClose();
    }

    boolean isOpen() {
        return getVisibility() == VISIBLE;
    }

    void release() {
        lyrics.release();
    }

    // ------------------------------------------------------------- 播放回调

    void onTrackChanged(@Nullable TvApi.Track track) {
        if (track == null || !isOpen()) return;
        bind(track);
    }

    private void bind(TvApi.Track track) {
        title.setText(track.title);
        subtitle.setText(subtitleOf(track));
        smallTitle.setText(track.title);
        smallSubtitle.setText(subtitleOf(track));
        bigCover.setImageDrawable(null);
        smallCover.setImageDrawable(null);
        if (track.hasCover()) {
            artwork.load(track.coverKey, bigCover);
            artwork.load(track.coverKey, smallCover);
            artwork.loadHires(track.coverKey, backdrop);
        } else {
            backdrop.setImageDrawable(null);
        }
        durationMs = track.durationMs;
        total.setText(TvApi.formatDuration(track.durationMs));
        elapsed.setText("0:00");
        seek.reset();
        singleLine.reset("正在载入歌词…");
        activeIndex = -1;
        lyrics.load(track);
        if (queueSheet.getVisibility() == View.VISIBLE) syncQueue();
    }

    private static String subtitleOf(TvApi.Track track) {
        return track.album == null || track.album.isEmpty()
                ? track.artist
                : track.artist + " · " + track.album;
    }

    void onPlayingChanged(boolean playing) {
        playButton.setText(playing ? "暂停" : "播放");
    }

    void onProgress(long positionMs, long totalMs) {
        if (!isOpen()) return;
        if (totalMs > 0) durationMs = totalMs;
        seek.setProgress(positionMs, durationMs);
        elapsed.setText(TvApi.formatDuration(positionMs));
        if (durationMs > 0) total.setText(TvApi.formatDuration(durationMs));

        int index = lyrics.hasTiming() ? lyrics.indexAt(positionMs) : -1;
        if (index == activeIndex) return;
        activeIndex = index;
        if (index >= 0 && index < currentLines.size()) {
            singleLine.setLine(currentLines.get(index).text);
            if (mode == MODE_LYRIC) lyricColumn.setActive(index);
        } else if (currentLines.isEmpty()) {
            singleLine.reset(lyrics.status().isEmpty() ? "暂无歌词" : lyrics.status());
        }
    }

    void onQueueChanged() {
        if (queueSheet.getVisibility() == View.VISIBLE) syncQueue();
    }

    // ------------------------------------------------------------- 歌词

    private void onLyricsUpdated() {
        List<TvLyricsParser.Line> lines = lyrics.lines();
        currentLines = lines;
        activeIndex = -1;
        if (lines.isEmpty()) {
            lyricColumn.showMessage(lyrics.status().isEmpty() ? "暂无歌词" : lyrics.status());
            singleLine.reset(lyrics.status().isEmpty() ? "暂无歌词" : lyrics.status());
            return;
        }
        lyricColumn.bind(lines);
        if (lyrics.hasTiming()) {
            onProgress(player.position(), durationMs);
        } else {
            singleLine.setLine(lines.get(0).text);
            lyricColumn.setActive(0);
        }
    }

    // ------------------------------------------------------------- 形态切换

    private void setMode(int value) {
        mode = value;
        boolean cover = value == MODE_COVER;
        coverStage.setVisibility(cover ? VISIBLE : GONE);
        lyricStage.setVisibility(cover ? GONE : VISIBLE);
        lyricsButton.setText(cover ? "歌词" : "封面");
        if (!cover) {
            lyricColumn.bind(currentLines);
            int index = lyrics.hasTiming() ? lyrics.indexAt(player.position()) : -1;
            activeIndex = index;
            lyricColumn.setActive(index);
        }
    }

    // ------------------------------------------------------------- 队列

    private void openQueue() {
        syncQueue();
        queueSheet.open();
    }

    private void syncQueue() {
        TvApi.Track current = player.current();
        queueSheet.bind(player.queue(), current == null ? "" : current.id, player.cursor());
    }

    // ------------------------------------------------------------- 按键

    /**
     * Remote keys for the page. Called by the shell before its own handling so
     * Back can unwind lyric mode first, then the page itself.
     */
    boolean handleKey(int keyCode, KeyEvent event) {
        if (!isOpen()) return false;
        if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
        if (queueSheet.getVisibility() == View.VISIBLE && queueSheet.handleKey(keyCode, event)) {
            return true;
        }
        switch (keyCode) {
            case KeyEvent.KEYCODE_BACK:
                if (mode == MODE_LYRIC) {
                    setMode(MODE_COVER);
                    lyricsButton.requestFocus();
                } else {
                    close();
                }
                return true;
            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
            case KeyEvent.KEYCODE_MEDIA_PLAY:
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                player.toggle();
                return true;
            case KeyEvent.KEYCODE_MEDIA_NEXT:
                player.next();
                return true;
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                player.previous();
                return true;
            default:
                return false;
        }
    }
}
