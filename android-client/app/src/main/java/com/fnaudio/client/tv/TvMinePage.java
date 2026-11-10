package com.fnaudio.client.tv;

import android.content.Context;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;

/**
 * 我的: the account's favourites and saved playlists.
 *
 * <p>One request ({@code /api/state/user}) carries both, so the page loads them
 * together and only splits them across two tabs. Favourites need a second call
 * to turn ids into tracks; a playlist is a card until it is opened, because its
 * tracks are fetched by the detail page.
 */
final class TvMinePage extends FrameLayout {
    interface OnPlay {
        void onPlay(TvApi.Track track, int index, List<TvApi.Track> queue);
    }

    interface OnOpenCard {
        void onOpenCard(TvCardItem item);
    }

    private static final String[] TABS = {"收藏", "播放列表"};

    private final TvApi api;
    private final ExecutorService io;
    private final TvChipTabs chips;
    private final TextView status;
    private final TvCardGrid favorites;
    private final TvCardGrid playlists;

    @Nullable private OnPlay playListener;
    @Nullable private OnOpenCard openListener;
    @Nullable private Runnable topEdgeListener;

    private boolean loaded;

    TvMinePage(Context context, TvApi api, TvArtworkLoader artwork, ExecutorService io) {
        super(context);
        this.api = api;
        this.io = io;

        chips = new TvChipTabs(context, TABS);
        chips.setOnSelected(this::showTab);
        addView(chips, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(context, 40f), Gravity.TOP));

        status = new TextView(context);
        status.setTextColor(TvTheme.TEXT_3);
        status.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        status.setGravity(Gravity.CENTER);
        status.setVisibility(GONE);
        addView(status, contentParams(context));

        favorites = new TvCardGrid(context, artwork);
        favorites.setEmptyText("还没有收藏\n在手机上给歌曲点个心");
        favorites.setOnTopEdge(this::focusChips);
        favorites.setOnOpen(item -> {
            if (item.track != null) {
                if (playListener != null) playListener.onPlay(item.track, 0, item.queue);
            } else if (openListener != null) {
                openListener.onOpenCard(item);
            }
        });
        addView(favorites, contentParams(context));

        playlists = new TvCardGrid(context, artwork);
        playlists.setEmptyText("还没有播放列表");
        playlists.setOnTopEdge(this::focusChips);
        playlists.setOnOpen(item -> {
            if (openListener != null) openListener.onOpenCard(item);
        });
        playlists.setVisibility(GONE);
        addView(playlists, contentParams(context));

        chips.setContentNextFocusDownId(favorites.getId());
        load();
    }

    private static FrameLayout.LayoutParams contentParams(Context context) {
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        params.topMargin = TvTheme.dp(context, 48f);
        return params;
    }

    void setOnPlay(OnPlay value) {
        this.playListener = value;
    }

    void setOnOpenCard(OnOpenCard value) {
        this.openListener = value;
    }

    void setOnTopEdge(Runnable value) {
        this.topEdgeListener = value;
        for (int index = 0; index < TABS.length; index++) {
            View chip = chips.itemAt(index);
            if (chip == null) continue;
            chip.setOnKeyListener((view, keyCode, event) -> {
                if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
                if (keyCode != KeyEvent.KEYCODE_DPAD_UP) return false;
                if (topEdgeListener == null) return false;
                topEdgeListener.run();
                return true;
            });
        }
    }

    void focusFirst() {
        View first = chips.selected() == 0 ? favorites.firstCard() : playlists.firstCard();
        if (first != null) first.requestFocus(); else chips.focusSelected();
    }

    private void focusChips() {
        chips.focusSelected();
    }

    private void showTab(int index) {
        favorites.setVisibility(index == 0 ? VISIBLE : GONE);
        playlists.setVisibility(index == 1 ? VISIBLE : GONE);
        View first = index == 0 ? favorites.firstCard() : playlists.firstCard();
        if (first != null) chips.setContentNextFocusDownId(first.getId());
    }

    private void load() {
        loaded = true;
        showStatus("正在载入账号数据…");
        io.execute(() -> {
            TvApi.UserState state = null;
            List<TvApi.Track> favoriteTracks = new ArrayList<>();
            String failure = null;
            try {
                state = api.userState();
                if (!state.favoriteIds.isEmpty()) {
                    favoriteTracks = api.tracksByIds(new ArrayList<>(state.favoriteIds));
                }
            } catch (IOException | RuntimeException error) {
                failure = error.getMessage();
            }
            final TvApi.UserState result = state;
            final List<TvApi.Track> tracks = favoriteTracks;
            final String error = failure;
            post(() -> {
                if (result == null) {
                    showStatus("账号数据载入失败\n" + (error == null ? "" : error));
                    return;
                }
                status.setVisibility(GONE);

                List<TvCardItem> favoritesCards = new ArrayList<>(tracks.size());
                for (TvApi.Track track : tracks) {
                    favoritesCards.add(TvCardItem.ofTrack(track, tracks));
                }
                favorites.setCards(favoritesCards);

                List<TvCardItem> playlistCards = new ArrayList<>(result.playlists.size());
                for (TvApi.Playlist playlist : result.playlists) {
                    playlistCards.add(TvCardItem.ofGroup("playlist:" + playlist.id, playlist.name,
                            playlist.trackIds.size() + " 首", ""));
                }
                playlists.setCards(playlistCards);

                View first = chips.selected() == 0 ? favorites.firstCard() : playlists.firstCard();
                if (first != null) {
                    chips.setContentNextFocusDownId(first.getId());
                    first.requestFocus();
                }
            });
        });
    }

    private void showStatus(String text) {
        status.setText(text);
        status.setVisibility(VISIBLE);
    }
}
