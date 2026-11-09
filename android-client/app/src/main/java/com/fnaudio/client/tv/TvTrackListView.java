package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.StateListDrawable;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;

/**
 * Vertical track list used by album, artist and "all tracks" pages.
 *
 * <p>Rows are 64dp tall so that roughly ten of them fit above the player bar on
 * a 1080p television; the focused row is the primary navigation affordance and
 * carries the same white ring as a card.
 */
final class TvTrackListView extends LinearLayout {
    interface OnTrackClick {
        void onTrackClick(TvApi.Track track, int position);
    }

    private final RecyclerView list;
    private final Adapter adapter;
    private final TextView empty;

    TvTrackListView(Context context, TvArtworkLoader loader) {
        super(context);
        setOrientation(VERTICAL);
        setPadding(TvUi.dp(context, 32), 0, TvUi.dp(context, 32), 0);

        list = new RecyclerView(context);
        list.setLayoutManager(new LinearLayoutManager(context));
        list.setItemAnimator(null);
        list.setClipToPadding(false);
        list.setPadding(0, TvUi.dp(context, 6), 0, TvUi.dp(context, 16));
        list.setFocusable(false);
        list.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);
        addView(list, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        empty = new TextView(context);
        empty.setText("这里还没有歌曲");
        empty.setTextColor(TvUi.TEXT_3);
        empty.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f);
        empty.setGravity(Gravity.CENTER);
        empty.setVisibility(GONE);
        addView(empty, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        adapter = new Adapter(loader);
        list.setAdapter(adapter);
    }

    void setTracks(List<TvApi.Track> tracks) {
        int focused = focusedPosition();
        adapter.submit(tracks);
        boolean isEmpty = tracks == null || tracks.isEmpty();
        list.setVisibility(isEmpty ? GONE : VISIBLE);
        empty.setVisibility(isEmpty ? VISIBLE : GONE);
        if (focused >= 0) restoreFocus(focused);
    }

    /** Adapter position of the row holding the focus, or -1. */
    private int focusedPosition() {
        View focus = list.findFocus();
        if (focus == null) return -1;
        View row = focus;
        while (row != null && row.getParent() != list) {
            if (!(row.getParent() instanceof View)) return -1;
            row = (View) row.getParent();
        }
        return row == null ? -1 : list.getChildAdapterPosition(row);
    }

    /** Re-focuses a row after its adapter data was replaced wholesale. */
    private void restoreFocus(int position) {
        list.post(() -> {
            RecyclerView.ViewHolder holder = list.findViewHolderForAdapterPosition(position);
            if (holder == null) holder = list.findViewHolderForAdapterPosition(0);
            if (holder != null && !holder.itemView.isFocused()) holder.itemView.requestFocus();
        });
    }

    void setOnTrackClick(OnTrackClick listener) {
        adapter.clickListener = listener;
    }

    /** Left on a row hands focus back to the rail. */
    void setOnLeftEdge(TvShelfView.OnEdge listener) {
        adapter.leftEdge = listener;
    }

    /** Marks the row that is currently audible. */
    void setNowPlayingId(String trackId) {
        String next = trackId == null ? "" : trackId;
        if (next.equals(adapter.currentId)) return;
        int previous = adapter.indexOf(adapter.currentId);
        adapter.currentId = next;
        int current = adapter.indexOf(next);
        // Only the two affected rows are rebound: a full invalidation would
        // rebuild every row and drop the highlight the viewer was standing on.
        if (previous >= 0) adapter.notifyItemChanged(previous);
        if (current >= 0) adapter.notifyItemChanged(current);
    }

    void focusFirst() {
        if (adapter.getItemCount() == 0) return;
        list.scrollToPosition(0);
        list.post(() -> {
            RecyclerView.ViewHolder holder = list.findViewHolderForAdapterPosition(0);
            if (holder != null) holder.itemView.requestFocus();
        });
    }

    RecyclerView list() {
        return list;
    }

    private static final class Adapter extends RecyclerView.Adapter<Adapter.Holder> {
        private final List<TvApi.Track> tracks = new ArrayList<>();
        private final TvArtworkLoader loader;
        OnTrackClick clickListener;
        TvShelfView.OnEdge leftEdge;
        String currentId = "";

        Adapter(TvArtworkLoader loader) {
            this.loader = loader;
        }

        void submit(List<TvApi.Track> next) {
            tracks.clear();
            if (next != null) tracks.addAll(next);
            notifyDataSetChanged();
        }

        int indexOf(String id) {
            for (int index = 0; index < tracks.size(); index++) {
                if (tracks.get(index).id.equals(id)) return index;
            }
            return -1;
        }

        @NonNull
        @Override public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            return new Holder(new RowView(parent.getContext()));
        }

        @Override public void onBindViewHolder(@NonNull Holder holder, int position) {
            TvApi.Track track = tracks.get(position);
            holder.row.bind(track, position + 1, track.id.equals(currentId));
            holder.row.loadArtwork(loader, track);
            holder.row.setOnClickListener(view -> {
                if (clickListener == null) return;
                int current = holder.getAdapterPosition();
                clickListener.onTrackClick(track, current < 0 ? position : current);
            });
            holder.row.setOnKeyListener((view, keyCode, event) -> {
                if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
                if (keyCode != KeyEvent.KEYCODE_DPAD_LEFT || leftEdge == null) return false;
                int current = holder.getAdapterPosition();
                if (current < 0) return false;
                return leftEdge.onEdge(current);
            });
        }

        @Override public int getItemCount() {
            return tracks.size();
        }

        static final class Holder extends RecyclerView.ViewHolder {
            final RowView row;

            Holder(RowView row) {
                super(row);
                this.row = row;
            }
        }
    }

    /** One row: index, thumbnail, title/artist, duration. */
    private static final class RowView extends LinearLayout {
        private final TextView index;
        private final ImageView cover;
        private final TextView title;
        private final TextView subtitle;
        private final TextView duration;

        RowView(Context context) {
            super(context);
            setOrientation(HORIZONTAL);
            setGravity(Gravity.CENTER_VERTICAL);
            setFocusable(true);
            setFocusableInTouchMode(false);
            setPadding(TvUi.dp(context, 12), 0, TvUi.dp(context, 16), 0);
            setLayoutParams(new RecyclerView.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(context, 56)));

            StateListDrawable background = new StateListDrawable();
            background.addState(new int[]{android.R.attr.state_focused},
                    TvUi.rounded(TvUi.PANEL_RAISED, 10f, context));
            background.addState(new int[]{}, TvUi.rounded(Color.TRANSPARENT, 10f, context));
            setBackground(background);
            setForeground(TvUi.focusRing(context, 10f));

            index = new TextView(context);
            index.setTextColor(TvUi.TEXT_3);
            index.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
            index.setGravity(Gravity.CENTER);
            index.setLayoutParams(new LayoutParams(TvUi.dp(context, 44),
                    ViewGroup.LayoutParams.WRAP_CONTENT));
            addView(index);

            FrameLayout coverFrame = new FrameLayout(context);
            coverFrame.setBackground(TvUi.rounded(TvUi.PANEL, 6f, context));
            LayoutParams coverParams = new LayoutParams(TvUi.dp(context, 44), TvUi.dp(context, 44));
            coverParams.rightMargin = TvUi.dp(context, 16);
            coverFrame.setLayoutParams(coverParams);
            addView(coverFrame);

            cover = new ImageView(context);
            cover.setScaleType(ImageView.ScaleType.CENTER_CROP);
            cover.setLayoutParams(new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            TvUi.roundClip(cover, 6f);
            coverFrame.addView(cover);

            LinearLayout labels = new LinearLayout(context);
            labels.setOrientation(VERTICAL);
            labels.setLayoutParams(new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            addView(labels);

            title = new TextView(context);
            title.setTextColor(TvUi.TEXT);
            title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
            title.setSingleLine(true);
            title.setEllipsize(TextUtils.TruncateAt.END);
            labels.addView(title);

            subtitle = new TextView(context);
            subtitle.setTextColor(TvUi.TEXT_3);
            subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f);
            subtitle.setSingleLine(true);
            subtitle.setEllipsize(TextUtils.TruncateAt.END);
            labels.addView(subtitle);

            duration = new TextView(context);
            duration.setTextColor(TvUi.TEXT_3);
            duration.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
            addView(duration);
        }

        void bind(TvApi.Track track, int number, boolean playing) {
            index.setText(playing ? "▶" : String.valueOf(number));
            index.setTextColor(playing ? TvUi.ACCENT : TvUi.TEXT_3);
            title.setText(track.title);
            StringBuilder detail = new StringBuilder(track.artist);
            if (!track.album.isEmpty() && !track.album.equals(track.title)) {
                detail.append(" · ").append(track.album);
            }
            if (!track.format.isEmpty()) detail.append(" · ").append(track.format);
            subtitle.setText(detail.toString());
            String length = TvApi.formatDuration(track.durationMs);
            duration.setText(length == null ? "" : length);
            Object tag = cover.getTag();
            if (track.coverKey != null && !track.coverKey.equals(tag)) {
                cover.setImageDrawable(null);
            }
        }

        void loadArtwork(TvArtworkLoader loader, TvApi.Track track) {
            loader.load(track.coverKey, cover);
        }
    }
}
