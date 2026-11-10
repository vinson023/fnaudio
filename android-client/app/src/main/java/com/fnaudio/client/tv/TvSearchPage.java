package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;

/**
 * 搜索: one text field, one button, one result list.
 *
 * <p>There is no on-screen alphabet here on purpose. The server's search is a
 * literal {@code LIKE} over title/artist/album with no pinyin index, so an
 * A-Z grid could only ever type Latin queries and would be useless on a
 * Chinese library. Instead the field hands the job to the device IME, whose
 * pinyin keyboard is already on every television box - the same choice both
 * reference clients make when they defer to the system keyboard.
 *
 * <p>Searching is explicit rather than as-you-type: every keystroke would put a
 * request on a NAS that may be transcoding at the time, and on a remote the
 * viewer types slowly anyway.
 */
final class TvSearchPage extends FrameLayout {
    interface OnPlay {
        void onPlay(TvApi.Track track, int index, List<TvApi.Track> queue);
    }

    private final TvApi api;
    private final ExecutorService io;
    private final EditText input;
    private final TextView submit;
    private final TvTrackList results;

    @Nullable private OnPlay playListener;
    @Nullable private Runnable topEdgeListener;

    TvSearchPage(Context context, TvApi api, ExecutorService io) {
        super(context);
        this.api = api;
        this.io = io;

        LinearLayout bar = new LinearLayout(context);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(TvTheme.dp(context, TvTheme.SCREEN_EDGE), TvTheme.dp(context, 8),
                TvTheme.dp(context, TvTheme.SCREEN_EDGE), TvTheme.dp(context, 8));
        addView(bar, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(context, 64f), Gravity.TOP));

        input = new EditText(context);
        input.setSingleLine(true);
        input.setTextColor(TvTheme.TEXT);
        input.setHintTextColor(TvTheme.TEXT_4);
        input.setHint("输入歌名、专辑或艺术家");
        input.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        input.setTypeface(Typeface.DEFAULT);
        input.setInputType(InputType.TYPE_CLASS_TEXT);
        input.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        input.setBackground(TvTheme.rounded(context, TvTheme.CARD_FILL, TvTheme.R_PILL));
        input.setPadding(TvTheme.dp(context, 20), 0, TvTheme.dp(context, 20), 0);
        input.setFocusable(true);
        input.setFocusableInTouchMode(true);
        input.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH
                    || (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                    && event.getAction() == KeyEvent.ACTION_DOWN)) {
                runSearch();
                return true;
            }
            return false;
        });
        bar.addView(input, new LinearLayout.LayoutParams(
                TvTheme.dp(context, 620), ViewGroup.LayoutParams.MATCH_PARENT));

        submit = new TextView(context);
        submit.setText("搜索");
        submit.setTextColor(TvTheme.TEXT);
        submit.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_SUB);
        submit.setGravity(Gravity.CENTER);
        submit.setSingleLine(true);
        submit.setFocusable(true);
        submit.setFocusableInTouchMode(false);
        submit.setPadding(TvTheme.dp(context, 24), 0, TvTheme.dp(context, 24), 0);
        submit.setBackground(TvTheme.cardBackground(context, TvTheme.R_PILL));
        submit.setForeground(TvTheme.focusRing(context, TvTheme.R_PILL));
        submit.setOnClickListener(view -> runSearch());
        LinearLayout.LayoutParams submitParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT);
        submitParams.leftMargin = TvTheme.dp(context, 14);
        bar.addView(submit, submitParams);

        results = new TvTrackList(context);
        results.setEmptyText("输入关键词，按 OK 开始搜索");
        results.setOnTopEdge(() -> input.requestFocus());
        results.setOnPick((track, index, queue) -> {
            if (playListener != null) playListener.onPlay(track, index, queue);
        });
        FrameLayout.LayoutParams resultParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        resultParams.topMargin = TvTheme.dp(context, 72f);
        addView(results, resultParams);

        input.setNextFocusRightId(submit.getId());
        submit.setNextFocusLeftId(input.getId());
        // Down from the field goes to the results, not to the button: on a
        // remote the button is the rarer of the two moves, so it is reached by
        // pressing Right once instead of being in the vertical path.
        input.setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
            if (keyCode != KeyEvent.KEYCODE_DPAD_UP) return false;
            if (topEdgeListener == null) return false;
            topEdgeListener.run();
            return true;
        });
    }

    void setOnPlay(OnPlay value) {
        this.playListener = value;
    }

    void setOnTopEdge(Runnable value) {
        this.topEdgeListener = value;
    }

    void focusFirst() {
        input.requestFocus();
    }

    private void runSearch() {
        String query = input.getText().toString().trim();
        hideKeyboard();
        if (query.isEmpty()) {
            results.setEmptyText("输入关键词，按 OK 开始搜索");
            results.setTracks(new ArrayList<>());
            return;
        }
        results.setEmptyText("正在搜索「" + query + "」…");
        results.setTracks(new ArrayList<>());
        io.execute(() -> {
            List<TvApi.Track> loaded = null;
            String failure = null;
            try {
                loaded = api.searchTracks(query, 100);
            } catch (IOException error) {
                failure = error.getMessage();
            }
            final List<TvApi.Track> result = loaded;
            final String error = failure;
            post(() -> {
                if (result == null) {
                    results.setEmptyText("搜索失败\n" + (error == null ? "" : error));
                    results.setTracks(new ArrayList<>());
                    return;
                }
                if (result.isEmpty()) {
                    results.setEmptyText("没有找到「" + query + "」");
                    results.setTracks(new ArrayList<>());
                    return;
                }
                results.setTracks(result);
                View first = results.firstRow();
                if (first != null) {
                    input.setNextFocusDownId(first.getId());
                    submit.setNextFocusDownId(first.getId());
                    first.requestFocus();
                }
            });
        });
    }

    private void hideKeyboard() {
        InputMethodManager manager =
                (InputMethodManager) getContext().getSystemService(Context.INPUT_METHOD_SERVICE);
        if (manager != null) manager.hideSoftInputFromWindow(input.getWindowToken(), 0);
    }
}
