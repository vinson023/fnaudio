package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Rect;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.Nullable;

import java.util.ArrayList;
import java.util.List;

/**
 * Recommendation page: a vertical stack of shelves.
 *
 * <p>Scrollable because a television shows roughly one and a half rows at
 * 960x540dp; the plan's prototype measured that and settled the first row's
 * height. Focus drives the scroll: a plain ScrollView does not follow the
 * highlight on its own, so the page listens for global focus changes and keeps
 * the focused card inside a 24dp margin.
 */
final class TvHomePage extends ScrollView {
    interface OnCardOpen {
        void onCardOpen(TvCardItem item);
    }

    private final TvArtworkLoader artwork;
    private final LinearLayout column;
    private final TextView status;
    private final List<TvFocusRow> rows = new ArrayList<>();
    private final ViewTreeObserver.OnGlobalFocusChangeListener focusWatcher;

    private OnCardOpen openListener;
    private Runnable topEdgeListener;

    TvHomePage(Context context, TvArtworkLoader artwork) {
        super(context);
        this.artwork = artwork;
        setFillViewport(true);
        setVerticalScrollBarEnabled(false);
        setClipToPadding(false);
        setClipChildren(false);
        setFocusable(false);
        setPadding(TvTheme.dp(context, TvTheme.SCREEN_EDGE), 0,
                TvTheme.dp(context, TvTheme.SCREEN_EDGE), TvTheme.dp(context, 24));

        column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setClipChildren(false);
        column.setClipToPadding(false);
        addView(column, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        status = new TextView(context);
        status.setTextColor(TvTheme.TEXT_3);
        status.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        status.setGravity(Gravity.CENTER);
        status.setPadding(0, TvTheme.dp(context, 96), 0, 0);
        column.addView(status);

        focusWatcher = this::onFocusMoved;
        getViewTreeObserver().addOnGlobalFocusChangeListener(focusWatcher);
    }

    void setOnCardOpen(OnCardOpen listener) {
        this.openListener = listener;
    }

    /** Up from the first shelf; the shell sends the highlight to the tab bar. */
    void setOnTopEdge(Runnable listener) {
        this.topEdgeListener = listener;
    }

    void showStatus(String message) {
        column.removeAllViews();
        rows.clear();
        status.setText(message);
        status.setVisibility(VISIBLE);
        column.addView(status);
    }

    /**
     * Renders the shelves.
     *
     * <p>{@code resumeTrack} / {@code resumePercent} prepend a "continue
     * playing" card to the first shelf instead of taking a row of its own. The
     * prototype showed an own row pushes the second shelf under the playback
     * bar with only 46px of it visible.
     */
    void render(List<TvShelfData.Shelf> shelves,
                @Nullable TvApi.Track resumeTrack, int resumePercent) {
        column.removeAllViews();
        rows.clear();

        if (shelves.isEmpty()) {
            status.setText("曲库还是空的\n先在手机上添加音乐");
            status.setVisibility(VISIBLE);
            column.addView(status);
            return;
        }

        for (int index = 0; index < shelves.size(); index++) {
            TvShelfData.Shelf shelf = shelves.get(index);
            TvFocusRow row = new TvFocusRow(getContext(), artwork, shelf.title);
            List<TvCardItem> cards = new ArrayList<>(shelf.cards);
            if (index == 0 && resumeTrack != null) {
                List<TvApi.Track> queue = new ArrayList<>();
                queue.add(resumeTrack);
                cards.add(0, TvCardItem.ofContinue(resumeTrack, queue, resumePercent));
            }
            row.setCards(cards);
            row.setOnCardClick((item, position) -> {
                if (openListener != null) openListener.onCardOpen(item);
            });
            row.setOnEdgeListener((position, direction) -> false);
            if (index == 0) {
                row.setOnTopEdge((position, direction) -> {
                    if (topEdgeListener == null) return false;
                    topEdgeListener.run();
                    return true;
                });
            }
            if (index > 0) {
                LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                params.topMargin = TvTheme.dp(getContext(), TvTheme.SHELF_GAP);
                row.setLayoutParams(params);
            }
            column.addView(row);
            rows.add(row);
        }
    }

    void focusFirst() {
        if (!rows.isEmpty()) rows.get(0).focusFirst();
    }

    @Nullable
    View firstFocusable() {
        if (rows.isEmpty()) return null;
        List<TvFocusCard> cards = rows.get(0).cards();
        return cards.isEmpty() ? null : cards.get(0);
    }

    @Override
    protected void onDetachedFromWindow() {
        if (getViewTreeObserver().isAlive()) {
            getViewTreeObserver().removeOnGlobalFocusChangeListener(focusWatcher);
        }
        super.onDetachedFromWindow();
    }

    private void onFocusMoved(View oldFocus, View newFocus) {
        if (newFocus == null || !isInside(newFocus)) return;
        Rect rect = new Rect();
        newFocus.getDrawingRect(rect);
        offsetDescendantRectToMyCoords(newFocus, rect);
        int margin = TvTheme.dp(getContext(), 24);
        int top = Math.max(0, rect.top - margin);
        int bottom = rect.bottom + margin;
        int scrollTop = getScrollY();
        int scrollBottom = scrollTop + getHeight();
        if (top < scrollTop) {
            smoothScrollTo(0, top);
        } else if (bottom > scrollBottom) {
            smoothScrollTo(0, Math.max(0, bottom - getHeight()));
        }
    }

    private boolean isInside(View view) {
        View parent = view;
        while (parent != null) {
            if (parent == this) return true;
            if (!(parent.getParent() instanceof View)) return false;
            parent = (View) parent.getParent();
        }
        return false;
    }
}
