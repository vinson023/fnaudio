package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * The scrolling lyric column of the player's lyric mode.
 *
 * <p>Measured from the reference clients: body 21sp, the active line 28sp and
 * bold, everything else at 66% white. It occupies 42.7% of the screen width and
 * 56.2% of its height on the right - the same box QQ music's
 * {@code activity_player_style_lyric} uses - so the cover keeps the left half
 * and the words keep the right one.
 *
 * <p>The column is deliberately not focusable and takes no keys: lyrics follow
 * playback. A remote that has to steer a lyric list is a remote the viewer will
 * press the wrong button on.
 */
final class TvLyricColumn extends FrameLayout {
    private static final float LINE_SP = 21f;
    private static final float ACTIVE_SP = 28f;
    /** Slack at both ends so the first and last line can still sit centred. */
    private static final float END_PADDING_DP = 120f;

    private final ScrollView scroller;
    private final LinearLayout rows;
    private final TextView message;
    private final List<TextView> lines = new ArrayList<>();

    private int active = -1;

    TvLyricColumn(Context context) {
        super(context);

        scroller = new ScrollView(context);
        scroller.setVerticalScrollBarEnabled(false);
        scroller.setFocusable(false);
        addView(scroller, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        rows = new LinearLayout(context);
        rows.setOrientation(LinearLayout.VERTICAL);
        rows.setPadding(0, TvTheme.dp(context, END_PADDING_DP),
                0, TvTheme.dp(context, END_PADDING_DP));
        scroller.addView(rows, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        message = new TextView(context);
        message.setTextColor(TvTheme.TEXT_4);
        message.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f);
        message.setGravity(Gravity.CENTER);
        message.setLineSpacing(TvTheme.dp(context, 8), 1f);
        message.setPadding(TvTheme.dp(context, 24), 0, TvTheme.dp(context, 24), 0);
        message.setVisibility(GONE);
        addView(message, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    void bind(List<TvLyricsParser.Line> parsed) {
        active = -1;
        lines.clear();
        rows.removeAllViews();
        message.setVisibility(GONE);
        scroller.setVisibility(VISIBLE);
        scroller.scrollTo(0, 0);
        for (TvLyricsParser.Line line : parsed) {
            TextView view = lineView(line.text);
            rows.addView(view);
            lines.add(view);
        }
    }

    /** Terminal state: the lookup answered, and there is nothing to scroll. */
    void showMessage(String text) {
        active = -1;
        lines.clear();
        rows.removeAllViews();
        scroller.setVisibility(GONE);
        message.setText(text);
        message.setVisibility(VISIBLE);
    }

    void clear() {
        showMessage("");
        message.setVisibility(GONE);
    }

    /** Lights {@code index} and scrolls it to the middle; -1 dims everything. */
    void setActive(int index) {
        if (index == active) return;
        int previous = active;
        active = index;
        if (previous >= 0 && previous < lines.size()) style(previous, false);
        if (index >= 0 && index < lines.size()) {
            style(index, true);
            centerOn(index);
        }
    }

    private TextView lineView(String text) {
        TextView view = new TextView(getContext());
        view.setText(text);
        view.setTextColor(TvTheme.TEXT_4);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, LINE_SP);
        view.setGravity(Gravity.CENTER);
        view.setLineSpacing(TvTheme.dp(getContext(), 4), 1f);
        view.setPadding(0, TvTheme.dp(getContext(), 6), 0, TvTheme.dp(getContext(), 6));
        view.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return view;
    }

    private void style(int index, boolean isActive) {
        TextView view = lines.get(index);
        view.setTextColor(isActive ? TvTheme.TEXT : TvTheme.TEXT_4);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, isActive ? ACTIVE_SP : LINE_SP);
        view.setTypeface(isActive ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
    }

    private void centerOn(final int index) {
        // Two passes: the active line just grew by 7sp, so the geometry that
        // matters only exists after this one has been laid out.
        rows.post(new Runnable() {
            @Override public void run() {
                if (index >= rows.getChildCount()) return;
                View line = rows.getChildAt(index);
                int target = line.getTop() + line.getHeight() / 2 - scroller.getHeight() / 2;
                scroller.smoothScrollTo(0, Math.max(0, target));
            }
        });
    }
}
