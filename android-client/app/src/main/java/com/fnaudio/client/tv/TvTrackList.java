package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.Nullable;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Vertical list of tracks: 52dp rows, index on the left, duration on the right.
 *
 * <p>One component serves the library's song tab, the search results and every
 * detail page, because they differ only in what fills them. Rows are plain
 * views rather than a RecyclerView: a local library is measured in hundreds of
 * tracks, and a recycler would have to keep re-focusing recycled rows while the
 * viewer holds down the D-pad.
 *
 * <p>52dp is the plan's compromise between the two reference list heights (QQ
 * 50 / NetEase 56); at 960x540 that shows eight rows above the player bar.
 */
final class TvTrackList extends FrameLayout {
    interface OnPick {
        /** {@code queue} is the full list, so the player can advance past the row. */
        void onPick(TvApi.Track track, int index, List<TvApi.Track> queue);
    }

    private final ScrollView scroller;
    private final LinearLayout column;
    private final TextView empty;
    private final List<TvApi.Track> tracks = new ArrayList<>();

    @Nullable private OnPick pickListener;
    @Nullable private Runnable topEdgeListener;

    TvTrackList(Context context) {
        super(context);
        setFocusable(false);

        scroller = new ScrollView(context);
        scroller.setFillViewport(true);
        scroller.setVerticalScrollBarEnabled(false);
        scroller.setClipToPadding(false);
        scroller.setFocusable(false);
        scroller.setPadding(TvTheme.dp(context, TvTheme.SCREEN_EDGE), 0,
                TvTheme.dp(context, TvTheme.SCREEN_EDGE), TvTheme.dp(context, 24));
        addView(scroller, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        scroller.addView(column, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        empty = new TextView(context);
        empty.setTextColor(TvTheme.TEXT_3);
        empty.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        empty.setGravity(Gravity.CENTER);
        empty.setPadding(0, TvTheme.dp(context, 96), 0, 0);
        empty.setVisibility(GONE);
        addView(empty, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    void setOnPick(OnPick value) {
        this.pickListener = value;
    }

    /** Up from the first row belongs to whatever is above the list. */
    void setOnTopEdge(Runnable value) {
        this.topEdgeListener = value;
    }

    void setEmptyText(String text) {
        empty.setText(text);
    }

    void setTracks(List<TvApi.Track> items) {
        tracks.clear();
        if (items != null) tracks.addAll(items);
        column.removeAllViews();
        if (tracks.isEmpty()) {
            empty.setVisibility(VISIBLE);
            return;
        }
        empty.setVisibility(GONE);
        for (int index = 0; index < tracks.size(); index++) {
            column.addView(row(index));
        }
    }

    void focusFirst() {
        if (column.getChildCount() > 0) column.getChildAt(0).requestFocus();
    }

    @Nullable
    View firstRow() {
        return column.getChildCount() == 0 ? null : column.getChildAt(0);
    }

    private View row(final int index) {
        final TvApi.Track track = tracks.get(index);
        LinearLayout row = new LinearLayout(getContext());
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setFocusable(true);
        row.setFocusableInTouchMode(false);
        row.setBackground(TvTheme.cardBackground(getContext(), 10f));
        row.setForeground(TvTheme.focusRing(getContext(), 10f));
        row.setPadding(TvTheme.dp(getContext(), 16), 0,
                TvTheme.dp(getContext(), 16), 0);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(getContext(), TvTheme.LIST_ROW_H));
        params.bottomMargin = TvTheme.dp(getContext(), 4);
        row.setLayoutParams(params);

        row.setOnClickListener(view -> {
            if (pickListener != null) pickListener.onPick(track, index, Collections.unmodifiableList(tracks));
        });
        row.setOnFocusChangeListener((view, hasFocus) -> view.animate()
                .scaleX(hasFocus ? 1.02f : 1f).scaleY(hasFocus ? 1.02f : 1f)
                .setDuration(TvTheme.FOCUS_MS).start());
        if (index == 0) {
            row.setOnKeyListener((view, keyCode, event) -> {
                if (event.getAction() != android.view.KeyEvent.ACTION_DOWN) return false;
                if (keyCode != android.view.KeyEvent.KEYCODE_DPAD_UP) return false;
                if (topEdgeListener == null) return false;
                topEdgeListener.run();
                return true;
            });
        }

        TextView number = new TextView(getContext());
        number.setText(String.valueOf(index + 1));
        number.setTextColor(TvTheme.TEXT_4);
        number.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        number.setTypeface(Typeface.MONOSPACE);
        number.setGravity(Gravity.CENTER);
        row.addView(number, new LinearLayout.LayoutParams(
                TvTheme.dp(getContext(), 40), ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout labels = new LinearLayout(getContext());
        labels.setOrientation(LinearLayout.VERTICAL);
        row.addView(labels, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView title = new TextView(getContext());
        title.setText(track.title);
        title.setTextColor(TvTheme.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        labels.addView(title);

        TextView artist = new TextView(getContext());
        artist.setText(track.artist);
        artist.setTextColor(TvTheme.TEXT_4);
        artist.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_SUB);
        artist.setSingleLine(true);
        artist.setEllipsize(TextUtils.TruncateAt.END);
        labels.addView(artist);

        View badge = formatBadge(track.format);
        if (badge != null) {
            LinearLayout.LayoutParams badgeParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            badgeParams.leftMargin = TvTheme.dp(getContext(), 12);
            badgeParams.rightMargin = TvTheme.dp(getContext(), 12);
            row.addView(badge, badgeParams);
        }

        TextView duration = new TextView(getContext());
        duration.setText(TvApi.formatDuration(track.durationMs));
        duration.setTextColor(TvTheme.TEXT_4);
        duration.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        duration.setTypeface(Typeface.MONOSPACE);
        row.addView(duration);

        return row;
    }

    /**
     * Format tag, only for formats a viewer distinguishes by eye.
     *
     * <p>FLAC and DSD are worth a badge on a hi-fi library; MP3 is the default
     * and labelling it would put a badge on almost every row.
     */
    @Nullable
    private View formatBadge(String format) {
        if (format == null) return null;
        String upper = format.toUpperCase(java.util.Locale.ROOT);
        if (!upper.contains("DSD") && !upper.contains("FLAC") && !upper.contains("DSF")
                && !upper.contains("WAV")) {
            return null;
        }
        TextView badge = new TextView(getContext());
        badge.setText(upper.contains("DSD") || upper.contains("DSF") ? "DSD" : upper);
        badge.setTextColor(TvTheme.ACCENT);
        badge.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        badge.setPadding(TvTheme.dp(getContext(), 6), TvTheme.dp(getContext(), 2),
                TvTheme.dp(getContext(), 6), TvTheme.dp(getContext(), 2));
        badge.setBackground(TvTheme.rounded(getContext(), TvTheme.ACCENT_SOFT, 6f));
        return badge;
    }
}
