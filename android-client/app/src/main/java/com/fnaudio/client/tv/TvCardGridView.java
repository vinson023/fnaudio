package com.fnaudio.client.tv;

import android.content.Context;
import android.view.ViewGroup;
import android.widget.LinearLayout;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;

/**
 * Album/artist grid for the browse pages.
 *
 * <p>Six columns is the widest layout that still keeps a 16sp title readable at
 * three metres on a 1080p panel; the grid itself has full D-pad support from
 * GridLayoutManager, so unlike the shelves it needs no custom navigation.
 */
final class TvCardGridView extends LinearLayout {
    private final RecyclerView grid;
    private final Adapter adapter;

    TvCardGridView(Context context, TvArtworkLoader loader, int spanCount, int cardWidthDp) {
        super(context);
        setOrientation(VERTICAL);
        setClipChildren(false);
        setPadding(TvUi.dp(context, 32), 0, TvUi.dp(context, 32), TvUi.dp(context, 16));
        grid = new RecyclerView(context);
        GridLayoutManager layout = new GridLayoutManager(context, spanCount);
        layout.setSpanSizeLookup(new GridLayoutManager.SpanSizeLookup() {
            @Override public int getSpanSize(int position) {
                return 1;
            }
        });
        grid.setLayoutManager(layout);
        grid.setItemAnimator(null);
        grid.setClipToPadding(false);
        grid.setPadding(0, TvUi.dp(context, 6), 0, TvUi.dp(context, 12));
        grid.setFocusable(false);
        grid.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);
        addView(grid, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        adapter = new Adapter(loader, cardWidthDp, spanCount);
        grid.setAdapter(adapter);
    }

    void setItems(List<TvShelfView.Item> items) {
        adapter.submit(items);
    }

    void setOnItemClick(TvShelfView.OnItemClick listener) {
        adapter.clickListener = listener;
    }

    void setOnLeftEdge(TvShelfView.OnEdge listener) {
        adapter.leftEdge = listener;
    }

    void focusFirst() {
        if (adapter.getItemCount() == 0) return;
        grid.scrollToPosition(0);
        grid.post(() -> {
            RecyclerView.ViewHolder holder = grid.findViewHolderForAdapterPosition(0);
            if (holder != null) holder.itemView.requestFocus();
        });
    }

    RecyclerView grid() {
        return grid;
    }

    private static final class Adapter extends RecyclerView.Adapter<Adapter.Holder> {
        private final List<TvShelfView.Item> items = new ArrayList<>();
        private final TvArtworkLoader loader;
        private final int cardWidthDp;
        private final int spanCount;
        TvShelfView.OnItemClick clickListener;
        TvShelfView.OnEdge leftEdge;

        Adapter(TvArtworkLoader loader, int cardWidthDp, int spanCount) {
            this.loader = loader;
            this.cardWidthDp = cardWidthDp;
            this.spanCount = spanCount;
        }

        void submit(List<TvShelfView.Item> next) {
            items.clear();
            if (next != null) items.addAll(next);
            notifyDataSetChanged();
        }

        @NonNull
        @Override public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            return new Holder(new TvCardView(parent.getContext(), cardWidthDp, true));
        }

        @Override public void onBindViewHolder(@NonNull Holder holder, int position) {
            TvShelfView.Item item = items.get(position);
            holder.card.bind(item.label, item.detail, item.coverKey, loader);
            holder.card.setOnClickListener(view -> {
                if (clickListener == null) return;
                int current = holder.getAdapterPosition();
                clickListener.onItemClick(item, current < 0 ? position : current);
            });
            holder.card.setOnKeyListener((view, keyCode, event) -> {
                // Left on the first column is the way back to the rail; without
                // this the grid swallows the key and the highlight stays put.
                if (event.getAction() != android.view.KeyEvent.ACTION_DOWN) return false;
                if (keyCode != android.view.KeyEvent.KEYCODE_DPAD_LEFT) return false;
                int current = holder.getAdapterPosition();
                if (current < 0 || current % spanCount != 0 || leftEdge == null) return false;
                return leftEdge.onEdge(current);
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
