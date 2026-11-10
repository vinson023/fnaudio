package com.fnaudio.client.tv;

import android.content.Context;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.List;

/**
 * "Up next" as a sheet over the player page, 46% wide and 68% tall.
 *
 * <p>The player page has no permanent side column: both references give the
 * screen to one subject and summon the queue on demand. A sheet also keeps the
 * focus graph small, which is the part that actually breaks on a remote.
 */
final class TvQueueSheet extends FrameLayout {
    interface OnPick {
        void onPick(int position);
    }

    interface OnClose {
        void onClose();
    }

    private final LinearLayout rows;
    private final ScrollView scroller;
    private final TextView heading;

    private OnPick pickListener;
    private OnClose closeListener;
    private int cursor;

    TvQueueSheet(Context context) {
        super(context);
        setVisibility(GONE);

        View scrim = new View(context);
        scrim.setBackgroundColor(0xB3000000);
        scrim.setFocusable(false);
        addView(scrim, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        int screenWidth = context.getResources().getDisplayMetrics().widthPixels;
        int screenHeight = context.getResources().getDisplayMetrics().heightPixels;
        int width = Math.round(screenWidth * 0.46f);
        int height = Math.round(screenHeight * 0.68f);

        LinearLayout panel = new LinearLayout(context);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setBackground(TvTheme.rounded(context, TvTheme.BG_ELEVATED, TvTheme.R_SHEET));
        panel.setPadding(TvTheme.dp(context, 24), TvTheme.dp(context, 20),
                TvTheme.dp(context, 24), TvTheme.dp(context, 16));

        heading = new TextView(context);
        heading.setTextColor(TvTheme.TEXT_2);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_SUB);
        heading.setLetterSpacing(0.08f);
        heading.setPadding(TvTheme.dp(context, 8), 0, 0, TvTheme.dp(context, 10));
        panel.addView(heading);

        scroller = new ScrollView(context);
        scroller.setVerticalScrollBarEnabled(false);
        scroller.setFocusable(false);
        panel.addView(scroller, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        rows = new LinearLayout(context);
        rows.setOrientation(LinearLayout.VERTICAL);
        scroller.addView(rows, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        FrameLayout.LayoutParams panelParams = new FrameLayout.LayoutParams(
                width, height, Gravity.END | Gravity.CENTER_VERTICAL);
        panelParams.rightMargin = TvTheme.dp(context, TvTheme.SCREEN_EDGE);
        addView(panel, panelParams);
    }

    void setOnPick(OnPick value) {
        this.pickListener = value;
    }

    void setOnClose(OnClose value) {
        this.closeListener = value;
    }

    void bind(List<TvApi.Track> tracks, String currentId, int cursor) {
        rows.removeAllViews();
        heading.setText("接下来 · " + tracks.size() + " 首");
        for (int index = 0; index < tracks.size(); index++) {
            rows.addView(row(tracks.get(index), index,
                    currentId != null && currentId.equals(tracks.get(index).id)));
        }
        this.cursor = cursor;
    }

    private View row(TvApi.Track track, int position, boolean current) {
        LinearLayout row = new LinearLayout(getContext());
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setFocusable(true);
        row.setFocusableInTouchMode(false);
        row.setBackground(TvTheme.cardBackground(getContext(), 10f));
        row.setForeground(TvTheme.focusRing(getContext(), 10f));
        row.setPadding(TvTheme.dp(getContext(), 12), TvTheme.dp(getContext(), 8),
                TvTheme.dp(getContext(), 14), TvTheme.dp(getContext(), 8));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(getContext(), TvTheme.LIST_ROW_H));
        params.bottomMargin = TvTheme.dp(getContext(), 4);
        row.setLayoutParams(params);
        row.setOnClickListener(view -> {
            if (pickListener != null) pickListener.onPick(position);
        });
        row.setOnFocusChangeListener((view, hasFocus) -> view.animate()
                .scaleX(hasFocus ? 1.02f : 1f).scaleY(hasFocus ? 1.02f : 1f)
                .setDuration(TvTheme.FOCUS_MS).start());

        TextView index = new TextView(getContext());
        index.setText(String.valueOf(position + 1));
        index.setTextColor(current ? TvTheme.ACCENT : TvTheme.TEXT_4);
        index.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        index.setGravity(Gravity.CENTER);
        index.setTypeface(android.graphics.Typeface.MONOSPACE);
        row.addView(index, new LinearLayout.LayoutParams(
                TvTheme.dp(getContext(), 30), ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout labels = new LinearLayout(getContext());
        labels.setOrientation(LinearLayout.VERTICAL);
        row.addView(labels, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView title = new TextView(getContext());
        title.setText(track.title);
        title.setTextColor(current ? TvTheme.ACCENT : TvTheme.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        labels.addView(title);

        TextView artist = new TextView(getContext());
        artist.setText(track.artist);
        artist.setTextColor(TvTheme.TEXT_4);
        artist.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        artist.setSingleLine(true);
        artist.setEllipsize(TextUtils.TruncateAt.END);
        labels.addView(artist);

        TextView duration = new TextView(getContext());
        duration.setText(TvApi.formatDuration(track.durationMs));
        duration.setTextColor(TvTheme.TEXT_4);
        duration.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        duration.setTypeface(android.graphics.Typeface.MONOSPACE);
        LinearLayout.LayoutParams durationParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        durationParams.leftMargin = TvTheme.dp(getContext(), 12);
        row.addView(duration, durationParams);

        return row;
    }

    void open() {
        setVisibility(VISIBLE);
        focusAt(cursor);
    }

    void close() {
        setVisibility(GONE);
    }

    void focusAt(final int position) {
        rows.post(() -> {
            if (position >= 0 && position < rows.getChildCount()) {
                rows.getChildAt(position).requestFocus();
            } else if (rows.getChildCount() > 0) {
                rows.getChildAt(0).requestFocus();
            }
        });
    }

    boolean handleKey(int keyCode, KeyEvent event) {
        if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
        if (keyCode != KeyEvent.KEYCODE_BACK) return false;
        close();
        if (closeListener != null) closeListener.onClose();
        return true;
    }
}
