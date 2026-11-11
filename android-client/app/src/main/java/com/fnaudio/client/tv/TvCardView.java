package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.StateListDrawable;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * One focusable tile: square cover, title, optional subtitle.
 *
 * <p>The focus ring is a foreground layer rather than a background swap so a
 * bright album cover stays readable while focused, and the label area does not
 * turn into a grey block — the first prototype did exactly that and it looked
 * like a rendering bug on a real screen.
 */
final class TvCardView extends LinearLayout {
    private final FrameLayout coverFrame;
    private final ImageView cover;
    private final TextView monogram;
    private final TextView title;
    private final TextView subtitle;

    TvCardView(Context context, int widthDp, boolean showSubtitle) {
        super(context);
        setOrientation(VERTICAL);
        setFocusable(true);
        setFocusableInTouchMode(false);
        setClipChildren(false);
        setClipToPadding(false);
        int pad = TvUi.dp(context, 6);
        setPadding(pad, pad, pad, pad);
        setLayoutParams(new ViewGroup.LayoutParams(
                TvUi.dp(context, widthDp), ViewGroup.LayoutParams.WRAP_CONTENT));

        StateListDrawable background = new StateListDrawable();
        background.addState(new int[]{android.R.attr.state_focused},
                TvUi.rounded(TvUi.PANEL_RAISED, 14f, context));
        background.addState(new int[]{}, TvUi.rounded(Color.TRANSPARENT, 14f, context));
        setBackground(background);
        setForeground(TvUi.focusRing(context, 14f));

        coverFrame = new FrameLayout(context);
        int coverSize = TvUi.dp(context, widthDp - 12);
        coverFrame.setLayoutParams(new LinearLayout.LayoutParams(coverSize, coverSize));
        coverFrame.setBackground(TvUi.rounded(TvUi.PANEL, 12f, context));
        addView(coverFrame);

        cover = new ImageView(context);
        cover.setScaleType(ImageView.ScaleType.CENTER_CROP);
        cover.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        TvUi.roundClip(cover, 12f);
        coverFrame.addView(cover);

        // An artist group or a track with no embedded art has no cover key at
        // all, and a blank tile reads as a broken image. A monogram keeps the
        // shelf looking deliberate instead.
        monogram = new TextView(context);
        monogram.setTextColor(TvUi.TEXT_3);
        monogram.setTextSize(TypedValue.COMPLEX_UNIT_SP, 30f);
        monogram.setTypeface(null, android.graphics.Typeface.BOLD);
        monogram.setGravity(Gravity.CENTER);
        monogram.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        monogram.setVisibility(GONE);
        coverFrame.addView(monogram);

        title = new TextView(context);
        title.setTextColor(TvUi.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        titleParams.topMargin = TvUi.dp(context, 10);
        title.setLayoutParams(titleParams);
        addView(title);

        subtitle = new TextView(context);
        subtitle.setTextColor(TvUi.TEXT_3);
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams subtitleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        subtitleParams.topMargin = TvUi.dp(context, 2);
        subtitle.setLayoutParams(subtitleParams);
        if (showSubtitle) addView(subtitle); else subtitle.setVisibility(GONE);

        TvUi.applyFocusScale(this, 1.06f);
    }

    void bind(String label, String detail, String coverKey, TvArtworkLoader loader) {
        title.setText(label == null ? "" : label);
        subtitle.setText(detail == null ? "" : detail);
        loader.load(coverKey, cover);
        boolean hasCover = coverKey != null && !coverKey.isEmpty();
        monogram.setVisibility(hasCover ? GONE : VISIBLE);
        if (!hasCover) monogram.setText(initial(label));
    }

    private static String initial(String label) {
        if (label == null || label.trim().isEmpty()) return "♪";
        String trimmed = label.trim();
        return trimmed.substring(0, trimmed.offsetByCodePoints(0, 1)).toUpperCase();
    }

}
