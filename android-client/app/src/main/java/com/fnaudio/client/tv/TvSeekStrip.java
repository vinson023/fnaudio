package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;

/**
 * The focusable progress strip of the player's control bar.
 *
 * <p>It exists as its own focus target for one reason: on the previous player
 * the transport row stole left/right for seeking, which made the sixth button in
 * that row unreachable from a remote. Here left/right always move the highlight
 * between buttons, and seeking happens only while this strip holds the focus -
 * one rule, no dead ends.
 */
final class TvSeekStrip extends FrameLayout {
    interface OnSeek {
        /** {@code direction} is -1 for back, +1 for forward. */
        void onSeek(int direction);
    }

    private final View track;
    private final View fill;

    private OnSeek onSeek;
    private long durationMs;

    TvSeekStrip(Context context) {
        super(context);
        setFocusable(true);
        setFocusableInTouchMode(false);
        setPadding(TvTheme.dp(context, 10), TvTheme.dp(context, 12),
                TvTheme.dp(context, 10), TvTheme.dp(context, 12));
        setForeground(TvTheme.focusRing(context, TvTheme.R_PILL));

        FrameLayout bar = new FrameLayout(context);
        addView(bar, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        track = new View(context);
        GradientDrawable trackShape = new GradientDrawable();
        trackShape.setColor(0x33FFFFFF);
        trackShape.setCornerRadius(TvTheme.dp(context, 4));
        track.setBackground(trackShape);
        bar.addView(track, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(context, 8),
                Gravity.CENTER_VERTICAL));

        fill = new View(context);
        GradientDrawable fillShape = new GradientDrawable();
        fillShape.setColor(TvTheme.ACCENT);
        fillShape.setCornerRadius(TvTheme.dp(context, 4));
        fill.setBackground(fillShape);
        LayoutParams fillParams = new LayoutParams(
                0, TvTheme.dp(context, 8), Gravity.CENTER_VERTICAL | Gravity.START);
        bar.addView(fill, fillParams);

        setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
            if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT) {
                if (onSeek != null) onSeek.onSeek(-1);
                return true;
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_RIGHT) {
                if (onSeek != null) onSeek.onSeek(1);
                return true;
            }
            return false;
        });
    }

    void setOnSeek(OnSeek value) {
        this.onSeek = value;
    }

    void setProgress(long positionMs, long totalMs) {
        if (totalMs > 0) durationMs = totalMs;
        long length = durationMs;
        post(() -> {
            int width = track.getWidth();
            ViewGroup.LayoutParams params = fill.getLayoutParams();
            params.width = length <= 0 ? 0
                    : (int) Math.max(0, Math.min(width, width * (positionMs / (double) length)));
            fill.setLayoutParams(params);
        });
    }

    /** Called when nothing is loaded, so the bar does not keep an old fill. */
    void reset() {
        durationMs = 0;
        ViewGroup.LayoutParams params = fill.getLayoutParams();
        params.width = 0;
        fill.setLayoutParams(params);
    }
}
