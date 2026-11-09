package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Outline;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.view.View;
import android.view.ViewOutlineProvider;

/**
 * Shared visual language for the TV client.
 *
 * <p>A television is read from three metres away, so the palette is darker and
 * the type is larger than the phone UI; spacing uses a 4dp grid and every
 * focusable surface carries a 3px pure-white ring, because a colour-only focus
 * cue disappears against an album cover of arbitrary colour.
 */
final class TvUi {
    static final int BG = 0xFF07080A;
    static final int PANEL = 0xFF14161A;
    static final int PANEL_RAISED = 0xFF1D2026;
    static final int TEXT = 0xFFF5F7FA;
    static final int TEXT_2 = 0xFFA7AEBB;
    static final int TEXT_3 = 0xFF7A828F;
    static final int ACCENT = 0xFF3B82F6;
    static final int FOCUS_RING = 0xFFFFFFFF;

    private TvUi() {
    }

    static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static int sp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().scaledDensity);
    }

    /** Round-rectangle background; {@code radiusDp <= 0} keeps it square. */
    static Drawable rounded(int color, float radiusDp, Context context) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.RECTANGLE);
        drawable.setColor(color);
        drawable.setCornerRadius(dp(context, radiusDp));
        return drawable;
    }

    /** Focus ring drawn as a foreground so it never hides the cover art. */
    static Drawable focusRing(Context context, float radiusDp) {
        StateListDrawable states = new StateListDrawable();
        states.addState(new int[]{android.R.attr.state_focused}, stroke(context, FOCUS_RING, radiusDp));
        states.addState(new int[]{android.R.attr.state_selected}, stroke(context, 0x99FFFFFF, radiusDp));
        states.addState(new int[]{}, transparent());
        return states;
    }

    private static Drawable stroke(Context context, int color, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.RECTANGLE);
        drawable.setColor(Color.TRANSPARENT);
        drawable.setCornerRadius(dp(context, radiusDp));
        drawable.setStroke(dp(context, 3f), color);
        return drawable;
    }

    private static Drawable transparent() {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(Color.TRANSPARENT);
        return drawable;
    }

    /** Clips a view to a rounded rectangle, used for cover art. */
    static void roundClip(View view, final float radiusDp) {
        final float radius = dp(view.getContext(), radiusDp);
        view.setClipToOutline(true);
        view.setOutlineProvider(new ViewOutlineProvider() {
            @Override public void getOutline(View target, Outline outline) {
                outline.setRoundRect(0, 0, target.getWidth(), target.getHeight(), radius);
            }
        });
    }

    /** The elevation-and-scale treatment every focused tile shares. */
    static void applyFocusScale(View view, float scale) {
        view.setOnFocusChangeListener((target, hasFocus) -> {
            float value = hasFocus ? scale : 1f;
            target.animate().scaleX(value).scaleY(value).setDuration(120).start();
            target.setElevation(hasFocus ? dp(target.getContext(), 14f) : 0f);
        });
    }

    /**
     * Hides the status and navigation bars. A television has neither, but the
     * emulator image and some TV sticks still reserve them, which shifted every
     * page down by a status-bar height.
     */
    static void hideSystemBars(android.app.Activity activity) {
        androidx.core.view.WindowInsetsControllerCompat controller =
                androidx.core.view.WindowCompat.getInsetsController(
                        activity.getWindow(), activity.getWindow().getDecorView());
        controller.hide(androidx.core.view.WindowInsetsCompat.Type.systemBars());
        controller.setSystemBarsBehavior(
                androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    }
}
