package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.Nullable;

/**
 * The single lyric line under the title in cover mode.
 *
 * <p>One line only: at three metres the words are a caption, not a document, so
 * the page shows what is being sung right now and lets the viewer press "歌词"
 * when they want the whole text. A line change fades out and in over 260ms
 * total, which is what both reference clients do - an instant swap reads as a
 * rendering glitch on a large panel.
 */
final class TvLyricLine extends TextView {
    private static final long OUT_MS = 110L;
    private static final long IN_MS = 150L;

    private String shown = "";

    TvLyricLine(Context context) {
        super(context);
        setTextColor(TvTheme.TEXT_2);
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f);
        setGravity(Gravity.START);
        setSingleLine(true);
        setEllipsize(android.text.TextUtils.TruncateAt.END);
        setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    /** Marks the line that is being sung; {@code null} dims to a placeholder. */
    void setLine(@Nullable String text) {
        String next = text == null ? "" : text.trim();
        if (next.equals(shown)) return;
        shown = next;
        animate().cancel();
        animate().alpha(0f).setDuration(OUT_MS).withEndAction(() -> {
            setText(next);
            setTextColor(next.isEmpty() ? TvTheme.TEXT_4 : TvTheme.TEXT_2);
            setTypeface(next.isEmpty() ? Typeface.DEFAULT : Typeface.DEFAULT_BOLD);
            animate().alpha(1f).setDuration(IN_MS).start();
        }).start();
    }

    /** Empties immediately, used when the track changes. */
    void reset(String placeholder) {
        animate().cancel();
        shown = placeholder;
        setAlpha(1f);
        setText(placeholder);
        setTextColor(TvTheme.TEXT_4);
        setTypeface(Typeface.DEFAULT);
    }
}
