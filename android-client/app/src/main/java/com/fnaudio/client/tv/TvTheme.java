package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;

/**
 * Design tokens for the rebuilt television client.
 *
 * <p>Every number here was derived from the two reference clients in
 * {@code references/TVapp/} and the 960x540dp viewport that a 1080p television
 * reports at 320dpi. Keeping them in one place is what makes the rest of the
 * rebuild mechanical: pages describe layout, this class owns look.
 *
 * <p>Naming follows the plan in {@code docs/TV_REBUILD_PLAN_R531.md} §8 so a
 * value can be traced back to its measurement. {@link TvUi} still exists for
 * the legacy screens; new code should not add tokens there.
 */
final class TvTheme {
    private TvTheme() {
    }

    // ------------------------------------------------------------------ 色板
    /** Page background, measured from both reference clients. */
    static final int BG = 0xFF080812;
    /** Raised surface: bottom bar, sheets. */
    static final int BG_ELEVATED = 0xFF12141C;
    /** Resting card fill, 16% white. Named FILL so it cannot collide with the
     *  card *width* token below, which is what the compiler caught first. */
    static final int CARD_FILL = 0x29FFFFFF;
    /** Focused card fill, 24% white. */
    static final int CARD_FOCUS = 0x3DFFFFFF;
    static final int TEXT = 0xFFFFFFFF;
    static final int TEXT_2 = 0xB3FFFFFF;
    static final int TEXT_3 = 0x99FFFFFF;
    static final int TEXT_4 = 0x66FFFFFF;
    static final int DIVIDER = 0x1AFFFFFF;
    /** fnAudio blue: the one colour both references reserve for "this is active". */
    static final int ACCENT = 0xFF3B82F6;
    static final int ACCENT_SOFT = 0x333B82F6;
    static final int DANGER = 0xFFFF5A5A;

    // ------------------------------------------------------------ 尺寸（dp）
    static final float SCREEN_EDGE = 48f;
    static final float TAB_BAR_H = 56f;
    static final float PLAYER_BAR_H = 64f;
    static final float SHELF_HEAD_H = 40f;
    static final float SHELF_GAP = 32f;
    static final float CARD = 210f;
    static final float CARD_GAP = 24f;
    static final float GRID_CARD = 198f;
    static final float LIST_ROW_H = 52f;
    static final float R_CARD = 15f;
    static final float R_COVER = 12f;
    static final float R_SHEET = 24f;
    static final float R_PILL = 18f;

    // ------------------------------------------------------------ 字号（sp）
    static final float TAB = 18f;
    static final float SHELF = 20f;
    static final float CARD_TITLE = 18f;
    static final float CARD_SUB = 14f;
    static final float LIST_TITLE = 18f;
    static final float LIST_SUB = 14f;
    static final float LIST_META = 12f;
    static final float PLAYER_TITLE = 21f;
    static final float PLAYER_SUB = 16f;
    static final float LYRIC_LINE = 18f;
    static final float LYRIC_ACTIVE = 28f;
    static final float HERO = 34f;

    // ------------------------------------------------------------ 动效
    /** Focus must feel attached to the remote; 140ms is the plan's number. */
    static final long FOCUS_MS = 140L;
    static final long TRANSITION_MS = 320L;
    static final float FOCUS_SCALE = 1.08f;
    static final float FOCUS_STROKE_DP = 3f;

    // ------------------------------------------------------------ 工具
    static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static int sp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().scaledDensity);
    }

    /** Round-rectangle fill. */
    static Drawable rounded(Context context, int color, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.RECTANGLE);
        drawable.setColor(color);
        drawable.setCornerRadius(dp(context, radiusDp));
        return drawable;
    }

    /**
     * White focus ring as a foreground, so it never hides the cover art.
     *
     * <p>A foreground rather than a background because the cover fills the
     * card: drawing the ring behind it made the ring invisible on dark covers,
     * which is exactly the case a viewer needs it for.
     */
    static Drawable focusRing(Context context, float radiusDp) {
        StateListDrawable states = new StateListDrawable();
        states.addState(new int[]{android.R.attr.state_focused},
                stroke(context, FOCUS_STROKE_DP, radiusDp));
        states.addState(new int[]{}, transparent());
        return states;
    }

    private static Drawable stroke(Context context, float widthDp, float radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.RECTANGLE);
        drawable.setColor(0x00000000);
        drawable.setCornerRadius(dp(context, radiusDp));
        drawable.setStroke(Math.max(2, dp(context, widthDp)), TEXT);
        return drawable;
    }

    private static Drawable transparent() {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(0x00000000);
        return drawable;
    }

    /** Two-state list background for cards and rows. */
    static Drawable cardBackground(Context context, float radiusDp) {
        StateListDrawable states = new StateListDrawable();
        states.addState(new int[]{android.R.attr.state_focused},
                rounded(context, CARD_FOCUS, radiusDp));
        states.addState(new int[]{}, rounded(context, CARD_FILL, radiusDp));
        return states;
    }
}
