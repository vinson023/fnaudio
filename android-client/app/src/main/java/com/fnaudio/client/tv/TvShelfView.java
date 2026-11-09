package com.fnaudio.client.tv;

import android.content.Context;
import android.util.TypedValue;
import android.view.KeyEvent;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;

/**
 * A heading plus one horizontal, focus-scrolling row.
 *
 * <p>Rows are deliberately not paginated: a television viewer scrolls a shelf
 * with the left and right keys, and stopping every six tiles to press "next"
 * is the single most disliked interaction in ten-foot UIs.
 */
final class TvShelfView extends LinearLayout {
    /** One tile; {@code payload} is whatever the page wants back on click. */
    static final class Item {
        final String label;
        final String detail;
        final String coverKey;
        final Object payload;

        Item(String label, String detail, String coverKey, Object payload) {
            this.label = label;
            this.detail = detail;
            this.coverKey = coverKey;
            this.payload = payload;
        }
    }

    interface OnItemClick {
        void onItemClick(Item item, int position);
    }

    /** Called when left is pressed on the first tile of the row. */
    interface OnEdge {
        boolean onEdge(int position);
    }

    private final RecyclerView row;
    private final Adapter adapter;
    private final TextView heading;

    TvShelfView(Context context, TvShelfNavigator navigator, TvArtworkLoader loader,
                String title, int cardWidthDp) {
        super(context);
        setOrientation(VERTICAL);
        setClipChildren(false);
        setClipToPadding(false);
        setPadding(TvUi.dp(context, 32), 0, 0, 0);

        heading = new TextView(context);
        heading.setText(title);
        heading.setTextColor(TvUi.TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f);
        heading.setPadding(0, TvUi.dp(context, 18), 0, TvUi.dp(context, 8));
        addView(heading);

        row = new RecyclerView(context);
        row.setLayoutManager(new LinearLayoutManager(context, RecyclerView.HORIZONTAL, false));
        row.setItemAnimator(null);
        row.setClipToPadding(false);
        row.setClipChildren(false);
        row.setFocusable(false);
        row.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);
        row.setPadding(0, TvUi.dp(context, 8), 0, TvUi.dp(context, 10));
        addView(row, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        adapter = new Adapter(navigator, loader, cardWidthDp, row);
        row.setAdapter(adapter);
        navigator.register(row);
    }

    void setItems(List<Item> items) {
        adapter.submit(items);
        int size = items == null ? 0 : items.size();
        setVisibility(size == 0 ? GONE : VISIBLE);
    }

    void setOnItemClick(OnItemClick listener) {
        adapter.clickListener = listener;
    }

    void setOnLeftEdge(OnEdge listener) {
        adapter.leftEdge = listener;
    }

    /** Focuses the first tile, used when a page opens. */
    void focusFirst() {
        if (adapter.getItemCount() == 0) return;
        row.scrollToPosition(0);
        row.post(() -> {
            RecyclerView.ViewHolder holder = row.findViewHolderForAdapterPosition(0);
            if (holder != null) holder.itemView.requestFocus();
        });
    }

    RecyclerView row() {
        return row;
    }

    private static final class Adapter extends RecyclerView.Adapter<Adapter.Holder> {
        private final TvShelfNavigator navigator;
        private final TvArtworkLoader loader;
        private final int cardWidthDp;
        private final RecyclerView owner;
        private final List<Item> items = new ArrayList<>();
        OnItemClick clickListener;
        OnEdge leftEdge;

        Adapter(TvShelfNavigator navigator, TvArtworkLoader loader, int cardWidthDp,
                RecyclerView owner) {
            this.navigator = navigator;
            this.loader = loader;
            this.cardWidthDp = cardWidthDp;
            this.owner = owner;
        }

        void submit(List<Item> next) {
            items.clear();
            if (next != null) items.addAll(next);
            notifyDataSetChanged();
        }

        @NonNull
        @Override public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            return new Holder(new TvCardView(parent.getContext(), cardWidthDp, true));
        }

        @Override public void onBindViewHolder(@NonNull Holder holder, int position) {
            Item item = items.get(position);
            holder.card.bind(item.label, item.detail, item.coverKey, loader);
            holder.card.setOnClickListener(view -> {
                if (clickListener == null) return;
                int current = holder.getAdapterPosition();
                clickListener.onItemClick(item, current < 0 ? position : current);
            });
            holder.card.setOnKeyListener((view, keyCode, event) -> {
                if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
                // getBindingAdapterPosition() arrived in RecyclerView 1.2; the
                // bundled version is 1.1.0, so the adapter position is read
                // through the older accessor and validated for NO_POSITION.
                int current = holder.getAdapterPosition();
                if (current == RecyclerView.NO_POSITION) return false;
                if (keyCode == KeyEvent.KEYCODE_DPAD_UP) {
                    return navigator.move(owner, current, -1);
                }
                if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
                    return navigator.move(owner, current, +1);
                }
                if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT && current == 0
                        && leftEdge != null) {
                    return leftEdge.onEdge(current);
                }
                return false;
            });
        }

        @Override public int getItemCount() {
            return items.size();
        }

        static final class Holder extends RecyclerView.ViewHolder {
            final TvCardView card;

            Holder(TvCardView card) {
                super(card);
                this.card = card;
            }
        }
    }
}
