package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * One horizontal shelf: a heading and a row of cards.
 *
 * <p>The row itself is a plain {@link HorizontalScrollView} rather than a
 * RecyclerView. A shelf holds at most a few dozen cards and each shelf is built
 * once per page load; recycling would add a view-holder contract and a focus
 * save/restore problem without saving anything measurable at this size.
 *
 * <p>Focused cards are scaled 8%, so both the scroll container and this layout
 * disable clipping: the grown card has to be allowed to overlap the row above
 * and below it, which is what makes the highlight read as "lifted".
 */
final class TvFocusRow extends LinearLayout {
    interface OnCardClick {
        void onCardClick(TvCardItem item, int index);
    }

    interface OnEdge {
        /** @return true when the edge was consumed. */
        boolean onEdge(int index, int direction);
    }

    private final TvArtworkLoader artwork;
    private final HorizontalScrollView scroller;
    private final LinearLayout track;
    private final TextView heading;
    private final List<TvFocusCard> cards = new ArrayList<>();

    private OnCardClick clickListener;
    private OnEdge edgeListener;
    private OnEdge topEdgeListener;

    TvFocusRow(Context context, TvArtworkLoader artwork, String title) {
        super(context);
        this.artwork = artwork;
        setOrientation(VERTICAL);
        setClipChildren(false);
        setClipToPadding(false);

        heading = new TextView(context);
        heading.setText(title);
        heading.setTextColor(TvTheme.TEXT_2);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.SHELF);
        heading.setTypeface(Typeface.DEFAULT, Typeface.NORMAL);
        heading.setSingleLine(true);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        addView(heading, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(context, TvTheme.SHELF_HEAD_H)));

        scroller = new HorizontalScrollView(context);
        scroller.setHorizontalScrollBarEnabled(false);
        scroller.setClipChildren(false);
        scroller.setClipToPadding(false);
        scroller.setFocusable(false);
        // Keep the focus with the cards: a focusable scroller would swallow one
        // press of the direction key before the row starts moving.
        scroller.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);
        LayoutParams scrollParams = new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        scrollParams.topMargin = TvTheme.dp(context, 4);
        addView(scroller, scrollParams);

        track = new LinearLayout(context);
        track.setOrientation(HORIZONTAL);
        track.setClipChildren(false);
        scroller.addView(track, new HorizontalScrollView.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    void setOnCardClick(OnCardClick listener) {
        this.clickListener = listener;
    }

    void setOnEdgeListener(OnEdge listener) {
        this.edgeListener = listener;
    }

    /**
     * Up on any card in this row.
     *
     * <p>The page marks its first row only: up from a lower shelf must still
     * move to the shelf above, while up from the top shelf belongs to the tab
     * bar. Geometry alone cannot tell those apart once cards are scaled.
     */
    void setOnTopEdge(OnEdge listener) {
        this.topEdgeListener = listener;
    }

    List<TvFocusCard> cards() {
        return cards;
    }

    /**
     * Replaces the row content.
     *
     * <p>Cards are created once and rebound afterwards. Rebuilding them on every
     * data change dropped the highlight whenever a shelf refreshed, because the
     * view that held focus had been removed from the hierarchy.
     */
    void setCards(List<TvCardItem> items) {
        while (cards.size() > items.size()) {
            TvFocusCard removed = cards.remove(cards.size() - 1);
            track.removeView(removed);
        }
        while (cards.size() < items.size()) {
            TvFocusCard card = new TvFocusCard(getContext(), artwork);
            int index = cards.size();
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            if (index > 0) params.leftMargin = TvTheme.dp(getContext(), TvTheme.CARD_GAP);
            card.setLayoutParams(params);
            card.setOnClickListener(view -> dispatchClick(card));
            attachEdgeKeys(card);
            track.addView(card);
            cards.add(card);
        }
        for (int index = 0; index < items.size(); index++) {
            cards.get(index).bind(items.get(index));
        }
        setVisibility(items.isEmpty() ? GONE : VISIBLE);
    }

    private void dispatchClick(TvFocusCard card) {
        if (clickListener == null) return;
        int index = cards.indexOf(card);
        TvCardItem item = card.item();
        if (item == null || index < 0) return;
        clickListener.onCardClick(item, index);
    }

    private void attachEdgeKeys(TvFocusCard card) {
        card.setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
            if (edgeListener == null) return false;
            int index = cards.indexOf(card);
            if (keyCode == KeyEvent.KEYCODE_DPAD_UP && topEdgeListener != null) {
                return topEdgeListener.onEdge(index, -1);
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT && index == 0) {
                return edgeListener.onEdge(index, -1);
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_RIGHT && index == cards.size() - 1) {
                return edgeListener.onEdge(index, 1);
            }
            return false;
        });
        card.setOnFocusChangeListener((view, hasFocus) -> {
            float scale = hasFocus ? TvTheme.FOCUS_SCALE : 1f;
            view.animate().scaleX(scale).scaleY(scale)
                    .setDuration(TvTheme.FOCUS_MS).start();
            view.setZ(hasFocus ? TvTheme.dp(getContext(), 6) : 0f);
            if (hasFocus) ensureVisible(view);
        });
    }

    /**
     * Scrolls the row so the focused card is fully inside the viewport.
     *
     * <p>Scrolling by a fixed step felt wrong at the ends: the last card could
     * never reach the left edge, so the next press looked stuck. This keeps the
     * card at the edge it is travelling towards.
     */
    private void ensureVisible(View card) {
        scroller.post(() -> {
            int cardLeft = card.getLeft();
            int cardRight = cardLeft + card.getWidth();
            int viewport = scroller.getWidth();
            int offset = scroller.getScrollX();
            if (cardLeft < offset) {
                scroller.smoothScrollTo(cardLeft, 0);
            } else if (cardRight > offset + viewport) {
                scroller.smoothScrollTo(cardRight - viewport, 0);
            }
        });
    }

    void focusFirst() {
        if (!cards.isEmpty()) cards.get(0).requestFocus();
    }

    void focusIndex(int index) {
        if (index >= 0 && index < cards.size()) cards.get(index).requestFocus();
    }
}
