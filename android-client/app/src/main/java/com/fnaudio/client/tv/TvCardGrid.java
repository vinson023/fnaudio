package com.fnaudio.client.tv;

import android.content.Context;
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
import java.util.List;

/**
 * Four-column grid of album / artist / playlist cards.
 *
 * <p>The card is 198dp, not the 210dp used by the home shelves: four 210dp cards
 * plus three 24dp gaps plus the two 48dp page margins come to 1008dp on a 960dp
 * viewport, which overflows by 48dp. 48 + 4x198 + 3x24 + 48 = 960 exactly.
 *
 * <p>Focus is wired by hand rather than left to geometric search. A grid of
 * scaled cards is exactly the case where {@code FocusFinder} picks a diagonal
 * neighbour, and the last column's right key would jump to whatever happens to
 * be closest instead of staying put.
 */
final class TvCardGrid extends FrameLayout {
    interface OnOpen {
        void onOpen(TvCardItem item);
    }

    private static final int COLUMNS = 4;

    private final TvArtworkLoader artwork;
    private final ScrollView scroller;
    private final LinearLayout rows;
    private final TextView empty;
    private final List<TvFocusCard> cards = new ArrayList<>();

    @Nullable private OnOpen openListener;
    @Nullable private Runnable topEdgeListener;
    private String emptyText = "这里还没有内容";

    TvCardGrid(Context context, TvArtworkLoader artwork) {
        super(context);
        this.artwork = artwork;
        setClipChildren(false);
        setFocusable(false);

        scroller = new ScrollView(context);
        scroller.setFillViewport(true);
        scroller.setVerticalScrollBarEnabled(false);
        scroller.setClipToPadding(false);
        scroller.setClipChildren(false);
        scroller.setFocusable(false);
        scroller.setPadding(TvTheme.dp(context, TvTheme.SCREEN_EDGE), 0,
                TvTheme.dp(context, TvTheme.SCREEN_EDGE), TvTheme.dp(context, 24));
        addView(scroller, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        rows = new LinearLayout(context);
        rows.setOrientation(LinearLayout.VERTICAL);
        rows.setClipChildren(false);
        scroller.addView(rows, new FrameLayout.LayoutParams(
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

    void setOnOpen(OnOpen value) {
        this.openListener = value;
    }

    void setOnTopEdge(Runnable value) {
        this.topEdgeListener = value;
    }

    void setEmptyText(String text) {
        this.emptyText = text;
        empty.setText(text);
    }

    void setCards(List<TvCardItem> items) {
        rows.removeAllViews();
        cards.clear();
        if (items == null || items.isEmpty()) {
            empty.setText(emptyText);
            empty.setVisibility(VISIBLE);
            return;
        }
        empty.setVisibility(GONE);

        for (int start = 0; start < items.size(); start += COLUMNS) {
            LinearLayout line = new LinearLayout(getContext());
            line.setOrientation(LinearLayout.HORIZONTAL);
            line.setClipChildren(false);
            line.setClipToPadding(false);
            if (start > 0) {
                LinearLayout.LayoutParams lineParams = new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                lineParams.topMargin = TvTheme.dp(getContext(), TvTheme.CARD_GAP);
                line.setLayoutParams(lineParams);
            }
            int end = Math.min(items.size(), start + COLUMNS);
            for (int index = start; index < end; index++) {
                TvFocusCard card = new TvFocusCard(getContext(), artwork, TvTheme.GRID_CARD);
                card.bind(items.get(index));
                LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(
                        TvTheme.dp(getContext(), TvTheme.GRID_CARD),
                        ViewGroup.LayoutParams.WRAP_CONTENT);
                if (index > start) cardParams.leftMargin = TvTheme.dp(getContext(), TvTheme.CARD_GAP);
                card.setLayoutParams(cardParams);
                card.setOnClickListener(view -> {
                    if (openListener == null) return;
                    TvCardItem item = card.item();
                    if (item != null) openListener.onOpen(item);
                });
                line.addView(card);
                cards.add(card);
            }
            rows.addView(line);
        }
        wireFocus(items.size());
    }

    /**
     * Row-major focus graph: left/right stay inside a line, up/down walk the
     * grid, and the first line hands Up to the tabs above.
     */
    private void wireFocus(int count) {
        for (int index = 0; index < count; index++) {
            TvFocusCard card = cards.get(index);
            int column = index % COLUMNS;
            int rowCards = Math.min(COLUMNS, count - (index - column));
            int left = column == 0 ? index : index - 1;
            int right = column == rowCards - 1 ? index : index + 1;
            card.setNextFocusLeftId(cards.get(left).getId());
            card.setNextFocusRightId(cards.get(right).getId());
            if (index >= COLUMNS) {
                card.setNextFocusUpId(cards.get(index - COLUMNS).getId());
            }
            if (index + COLUMNS < count) {
                card.setNextFocusDownId(cards.get(index + COLUMNS).getId());
            }
        }
        TvFocusCard first = cards.get(0);
        first.setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() != android.view.KeyEvent.ACTION_DOWN) return false;
            if (keyCode != android.view.KeyEvent.KEYCODE_DPAD_UP) return false;
            if (topEdgeListener == null) return false;
            topEdgeListener.run();
            return true;
        });
    }

    void focusFirst() {
        if (!cards.isEmpty()) cards.get(0).requestFocus();
    }

    @Nullable
    View firstCard() {
        return cards.isEmpty() ? null : cards.get(0);
    }
}
