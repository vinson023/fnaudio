package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Always-on playback bar, 64dp tall.
 *
 * <p>Both reference clients keep a persistent bar at the bottom of the browse
 * screens; it is the only way to leave the player without losing the sense of
 * what is playing. The bar collapses to {@code GONE} when nothing has been
 * played yet, and the content area grows into the freed 64dp because the shell
 * pads the page container by the bar height only while it is visible.
 */
final class TvPlayerBar extends LinearLayout {
    interface OnAction {
        void onOpen();

        void onNext();

        void onToggle();
    }

    private final ImageView cover;
    private final TextView title;
    private final TextView subtitle;
    private final TextView elapsed;
    private final TextView total;
    private final View progressFill;
    private final View progressTrack;
    private final TextView playLabel;

    private OnAction action;
    private int durationMs;

    TvPlayerBar(Context context) {
        super(context);
        setOrientation(HORIZONTAL);
        setGravity(Gravity.CENTER_VERTICAL);
        setBackgroundColor(TvTheme.BG_ELEVATED);
        setPadding(TvTheme.dp(context, TvTheme.SCREEN_EDGE), 0,
                TvTheme.dp(context, TvTheme.SCREEN_EDGE), 0);
        setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(context, TvTheme.PLAYER_BAR_H)));

        LinearLayout left = new LinearLayout(context);
        left.setOrientation(HORIZONTAL);
        left.setGravity(Gravity.CENTER_VERTICAL);
        left.setFocusable(true);
        left.setFocusableInTouchMode(false);
        left.setBackground(TvTheme.rounded(context, 0x00000000, TvTheme.R_PILL));
        left.setForeground(TvTheme.focusRing(context, TvTheme.R_PILL));
        left.setPadding(TvTheme.dp(context, 4), 0, TvTheme.dp(context, 16), 0);
        left.setOnClickListener(view -> {
            if (action != null) action.onOpen();
        });
        left.setOnFocusChangeListener((view, hasFocus) -> view.animate()
                .scaleX(hasFocus ? 1.03f : 1f).scaleY(hasFocus ? 1.03f : 1f)
                .setDuration(TvTheme.FOCUS_MS).start());
        addView(left, new LinearLayout.LayoutParams(
                TvTheme.dp(context, 400), ViewGroup.LayoutParams.MATCH_PARENT));

        FrameLayout coverBox = new FrameLayout(context);
        coverBox.setBackground(TvTheme.rounded(context, 0xFF1A1D26, 8f));
        TvUi.roundClip(coverBox, 8f);
        LinearLayout.LayoutParams coverParams =
                new LinearLayout.LayoutParams(TvTheme.dp(context, 40), TvTheme.dp(context, 40));
        coverParams.rightMargin = TvTheme.dp(context, 14);
        left.addView(coverBox, coverParams);

        cover = new ImageView(context);
        cover.setScaleType(ImageView.ScaleType.CENTER_CROP);
        coverBox.addView(cover, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout labels = new LinearLayout(context);
        labels.setOrientation(VERTICAL);
        labels.setGravity(Gravity.CENTER_VERTICAL);
        left.addView(labels, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));

        title = new TextView(context);
        title.setTextColor(TvTheme.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        labels.addView(title);

        subtitle = new TextView(context);
        subtitle.setTextColor(TvTheme.TEXT_3);
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.CARD_SUB);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(TextUtils.TruncateAt.END);
        labels.addView(subtitle);

        LinearLayout progressArea = new LinearLayout(context);
        progressArea.setOrientation(HORIZONTAL);
        progressArea.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams progressParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        progressParams.leftMargin = TvTheme.dp(context, 24);
        progressParams.rightMargin = TvTheme.dp(context, 24);
        addView(progressArea, progressParams);

        elapsed = timeLabel(context);
        progressArea.addView(elapsed);

        FrameLayout progressBox = new FrameLayout(context);
        LinearLayout.LayoutParams trackParams = new LinearLayout.LayoutParams(
                0, TvTheme.dp(context, 3), 1f);
        trackParams.leftMargin = TvTheme.dp(context, 12);
        trackParams.rightMargin = TvTheme.dp(context, 12);
        progressArea.addView(progressBox, trackParams);

        progressTrack = new View(context);
        progressTrack.setBackgroundColor(0x24FFFFFF);
        progressBox.addView(progressTrack, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        progressFill = new View(context);
        GradientDrawable fill = new GradientDrawable();
        fill.setColor(TvTheme.ACCENT);
        fill.setCornerRadius(TvTheme.dp(context, 2));
        progressFill.setBackground(fill);
        progressBox.addView(progressFill, new FrameLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT));

        total = timeLabel(context);
        progressArea.addView(total);

        TextView next = barButton(context, "下一首");
        next.setOnClickListener(view -> {
            if (action != null) action.onNext();
        });
        LinearLayout.LayoutParams nextParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        nextParams.leftMargin = TvTheme.dp(context, 24);
        addView(next, nextParams);

        TextView play = barButton(context, "暂停");
        playLabel = play;
        play.setOnClickListener(view -> {
            if (action != null) action.onToggle();
        });
        LinearLayout.LayoutParams playParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        playParams.leftMargin = TvTheme.dp(context, 12);
        addView(play, playParams);
    }

    private TextView timeLabel(Context context) {
        TextView label = new TextView(context);
        label.setText("0:00");
        label.setTextColor(TvTheme.TEXT_4);
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        label.setTypeface(android.graphics.Typeface.MONOSPACE);
        return label;
    }

    private TextView barButton(Context context, String text) {
        TextView button = new TextView(context);
        button.setText(text);
        button.setTextColor(TvTheme.TEXT);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.CARD_SUB);
        button.setGravity(Gravity.CENTER);
        button.setSingleLine(true);
        button.setFocusable(true);
        button.setFocusableInTouchMode(false);
        button.setPadding(TvTheme.dp(context, 16), TvTheme.dp(context, 8),
                TvTheme.dp(context, 16), TvTheme.dp(context, 8));
        button.setBackground(TvTheme.cardBackground(context, TvTheme.R_PILL));
        button.setForeground(TvTheme.focusRing(context, TvTheme.R_PILL));
        return button;
    }

    void setOnAction(OnAction value) {
        this.action = value;
    }

    void bind(TvApi.Track track, TvArtworkLoader artwork, boolean playing) {
        if (track == null) {
            setVisibility(GONE);
            return;
        }
        setVisibility(VISIBLE);
        title.setText(track.title);
        subtitle.setText(track.artist);
        cover.setImageDrawable(null);
        if (!track.coverKey.isEmpty()) artwork.load(track.coverKey, cover);
        durationMs = (int) Math.max(0, track.durationMs);
        playLabel.setText(playing ? "暂停" : "播放");
        setProgress(0, durationMs);
    }

    void setPlaying(boolean playing) {
        playLabel.setText(playing ? "暂停" : "播放");
    }

    void setProgress(long positionMs, long totalMs) {
        long length = totalMs > 0 ? totalMs : durationMs;
        if (length > 0) durationMs = (int) length;
        elapsed.setText(orZero(TvApi.formatDuration(Math.max(0, positionMs))));
        total.setText(orZero(TvApi.formatDuration(Math.max(0, length))));
        progressFill.post(() -> {
            ViewGroup.LayoutParams params = progressFill.getLayoutParams();
            params.width = length <= 0 ? 0
                    : Math.round(progressTrack.getWidth()
                            * Math.min(1f, positionMs / (float) length));
            progressFill.setLayoutParams(params);
        });
    }

    void focusFirst() {
        View first = getChildAt(0);
        if (first != null) first.requestFocus();
    }

    private static String orZero(String value) {
        return value == null ? "0:00" : value;
    }
}
