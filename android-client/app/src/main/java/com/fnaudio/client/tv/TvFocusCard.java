package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
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
 * One card in a horizontal shelf: cover, title, subtitle.
 *
 * <p>Sized from the measured 210dp reference card. The cover is 186dp inside a
 * 12dp inset, the title is 18sp and the subtitle 14sp — a full step larger than
 * the legacy TV screens, which were laid out for a desktop viewing distance.
 *
 * <p>Focus raises the card by {@link TvTheme#FOCUS_SCALE} and draws a 3dp white
 * ring as a foreground. The ring must be a foreground: covers of arbitrary
 * colour would swallow a background stroke.
 */
final class TvFocusCard extends LinearLayout {
    /** Width of a shelf card in dp; the grid page uses its own narrower width. */
    static final float WIDTH_DP = TvTheme.CARD;

    private final TvArtworkLoader artwork;
    private final FrameLayout coverBox;
    private final ImageView cover;
    private final TextView monogram;
    private final TextView title;
    private final TextView subtitle;
    private final View progressTrack;
    private final View progressFill;
    private final TextView badge;

    private TvCardItem item;

    TvFocusCard(Context context, TvArtworkLoader artwork) {
        this(context, artwork, WIDTH_DP);
    }

    TvFocusCard(Context context, TvArtworkLoader artwork, float widthDp) {
        super(context);
        this.artwork = artwork;
        setOrientation(VERTICAL);
        setPadding(TvTheme.dp(context, 12), TvTheme.dp(context, 12),
                TvTheme.dp(context, 12), TvTheme.dp(context, 12));
        setFocusable(true);
        setFocusableInTouchMode(false);
        setBackground(TvTheme.cardBackground(context, TvTheme.R_CARD));
        setForeground(TvTheme.focusRing(context, TvTheme.R_CARD));
        setLayoutParams(new ViewGroup.LayoutParams(
                TvTheme.dp(context, widthDp), ViewGroup.LayoutParams.WRAP_CONTENT));

        float coverDp = widthDp - 24f;

        coverBox = new FrameLayout(context);
        coverBox.setBackground(TvTheme.rounded(context, 0xFF1A1D26, TvTheme.R_COVER));
        TvUi.roundClip(coverBox, TvTheme.R_COVER);
        addView(coverBox, new LayoutParams(
                TvTheme.dp(context, coverDp), TvTheme.dp(context, coverDp)));

        monogram = new TextView(context);
        monogram.setTextColor(0x66FFFFFF);
        monogram.setTextSize(TypedValue.COMPLEX_UNIT_SP, 44f);
        monogram.setGravity(Gravity.CENTER);
        monogram.setTypeface(Typeface.DEFAULT_BOLD);
        coverBox.addView(monogram, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        cover = new ImageView(context);
        cover.setScaleType(ImageView.ScaleType.CENTER_CROP);
        coverBox.addView(cover, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        badge = new TextView(context);
        badge.setTextColor(0xFFFFFFFF);
        badge.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        badge.setBackground(TvTheme.rounded(context, 0x8C000000, 11f));
        badge.setPadding(TvTheme.dp(context, 9), TvTheme.dp(context, 3),
                TvTheme.dp(context, 9), TvTheme.dp(context, 3));
        badge.setVisibility(GONE);
        FrameLayout.LayoutParams badgeParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.START | Gravity.TOP);
        badgeParams.leftMargin = TvTheme.dp(context, 8);
        badgeParams.topMargin = TvTheme.dp(context, 8);
        coverBox.addView(badge, badgeParams);

        progressTrack = new View(context);
        progressTrack.setBackgroundColor(0x33FFFFFF);
        progressTrack.setVisibility(GONE);
        FrameLayout.LayoutParams trackParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(context, 4), Gravity.BOTTOM);
        coverBox.addView(progressTrack, trackParams);

        progressFill = new View(context);
        GradientDrawable fill = new GradientDrawable();
        fill.setColor(TvTheme.ACCENT);
        progressFill.setBackground(fill);
        progressFill.setVisibility(GONE);
        FrameLayout.LayoutParams fillParams = new FrameLayout.LayoutParams(
                0, TvTheme.dp(context, 4), Gravity.BOTTOM | Gravity.START);
        coverBox.addView(progressFill, fillParams);

        title = new TextView(context);
        title.setTextColor(TvTheme.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.CARD_TITLE);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        LayoutParams titleParams = new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        titleParams.topMargin = TvTheme.dp(context, 8);
        addView(title, titleParams);

        subtitle = new TextView(context);
        subtitle.setTextColor(TvTheme.TEXT_3);
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.CARD_SUB);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(TextUtils.TruncateAt.END);
        LayoutParams subParams = new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        subParams.topMargin = TvTheme.dp(context, 2);
        addView(subtitle, subParams);

        // Lift the focused card above its neighbours without reordering the
        // row: bringToFront() would move the child and break the shelf layout.
        setOnFocusChangeListener((view, hasFocus) -> {
            float scale = hasFocus ? TvTheme.FOCUS_SCALE : 1f;
            view.animate().scaleX(scale).scaleY(scale)
                    .setDuration(TvTheme.FOCUS_MS).start();
            view.setZ(hasFocus ? TvTheme.dp(context, 6) : 0f);
        });
    }

    /** Replaces the width, used by the four-column grid page. */
    void setCardWidth(float widthDp) {
        ViewGroup.LayoutParams params = getLayoutParams();
        params.width = TvTheme.dp(getContext(), widthDp);
        setLayoutParams(params);
        int coverDp = TvTheme.dp(getContext(), widthDp - 24f);
        ViewGroup.LayoutParams coverParams = coverBox.getLayoutParams();
        coverParams.width = coverDp;
        coverParams.height = coverDp;
        coverBox.setLayoutParams(coverParams);
    }

    void bind(TvCardItem value) {
        this.item = value;
        title.setText(value.title);
        subtitle.setText(value.subtitle.isEmpty() ? " " : value.subtitle);
        monogram.setText(firstGlyph(value.title));
        cover.setImageDrawable(null);
        if (value.coverKey != null && !value.coverKey.isEmpty()) {
            artwork.load(value.coverKey, cover);
        }
        setContentDescription(value.title + " " + value.subtitle);
        if (value.continueCard) {
            badge.setText("继续播放");
            badge.setVisibility(VISIBLE);
            progressTrack.setVisibility(VISIBLE);
            progressFill.setVisibility(VISIBLE);
            FrameLayout.LayoutParams fillParams =
                    (FrameLayout.LayoutParams) progressFill.getLayoutParams();
            fillParams.width = 0;
            progressFill.setLayoutParams(fillParams);
            progressFill.post(() -> {
                int track = progressTrack.getWidth();
                int percent = Math.max(4, Math.min(100, value.progressPercent));
                FrameLayout.LayoutParams params =
                        (FrameLayout.LayoutParams) progressFill.getLayoutParams();
                params.width = Math.round(track * percent / 100f);
                progressFill.setLayoutParams(params);
            });
        } else {
            badge.setVisibility(GONE);
            progressTrack.setVisibility(GONE);
            progressFill.setVisibility(GONE);
        }
    }

    TvCardItem item() {
        return item;
    }

    private static String firstGlyph(String text) {
        if (text == null || text.trim().isEmpty()) return "♪";
        String trimmed = text.trim();
        return trimmed.substring(0, 1);
    }
}
