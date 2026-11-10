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
 * 资料库: songs, albums and artists behind a 40dp secondary tab row.
 *
 * <p>Songs are a list because a viewer scans titles; albums and artists are a
 * grid because a viewer recognises covers. Those are the only two shapes the
 * three tabs need, so they share {@link TvTrackList} and {@link TvCardGrid}
 * rather than each getting a bespoke layout.
 *
 * <p>Each tab loads on first visit and is then kept. A local library answers in
 * milliseconds, but re-fetching on every tab switch would still throw away the
 * scroll position and the highlight.
 */
final class TvLibraryPage extends FrameLayout {
    interface OnPlay {
        void onPlay(TvApi.Track track, int index, List<TvApi.Track> queue);
    }

    interface OnOpenCard {
        void onOpenCard(TvCardItem item);
    }

    private static final String[] TABS = {"歌曲", "专辑", "艺术家"};

    private final TvApi api;
    private final ExecutorService io;
    private final TvChipTabs chips;
    private final TextView status;
    private final TvTrackList songs;
    private final TvCardGrid albums;
    private final TvCardGrid artists;

    @Nullable private OnPlay playListener;
    @Nullable private OnOpenCard openListener;
    @Nullable private Runnable topEdgeListener;

    private boolean songsLoaded;
    private boolean albumsLoaded;
    private boolean artistsLoaded;

    TvLibraryPage(Context context, TvApi api, TvArtworkLoader artwork, ExecutorService io) {
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

        songs = new TvTrackList(context);
        songs.setEmptyText("曲库还是空的\n先在手机上添加音乐");
        songs.setOnTopEdge(this::focusChips);
        songs.setOnPick((track, index, queue) -> {
            if (playListener != null) playListener.onPlay(track, index, queue);
        });
        addView(songs, contentParams(context));

        albums = new TvCardGrid(context, artwork);
        albums.setEmptyText("还没有专辑");
        albums.setOnTopEdge(this::focusChips);
        albums.setOnOpen(this::dispatchCard);
        albums.setVisibility(GONE);
        addView(albums, contentParams(context));

        artists = new TvCardGrid(context, artwork);
        artists.setEmptyText("还没有艺术家");
        artists.setOnTopEdge(this::focusChips);
        artists.setOnOpen(this::dispatchCard);
        artists.setVisibility(GONE);
        addView(artists, contentParams(context));

        // The chip row selects index 0 silently at construction, so nothing has
        // asked for the song list yet. Load it here rather than waiting for the
        // first Down key, which would show an empty page until then.
        showTab(0);
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

    /** Up from the chip row: the shell takes the highlight to the main tabs. */
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

    /**
     * Land on the first item, not on the tab row.
     *
     * <p>Opening a page and landing on its tabs makes the viewer press Down
     * before anything responds; both reference clients open on content and
     * leave the tabs one Up away.
     */
    void focusFirst() {
        View first = firstOfCurrentTab();
        if (first != null) first.requestFocus(); else chips.focusSelected();
    }

    private void focusChips() {
        chips.focusSelected();
    }

    private void dispatchCard(TvCardItem item) {
        if (openListener != null) openListener.onOpenCard(item);
    }

    private void showTab(int index) {
        songs.setVisibility(index == 0 ? VISIBLE : GONE);
        albums.setVisibility(index == 1 ? VISIBLE : GONE);
        artists.setVisibility(index == 2 ? VISIBLE : GONE);
        status.setVisibility(GONE);
        if (index == 0 && !songsLoaded) loadSongs();
        if (index == 1 && !albumsLoaded) loadGroups(albums, true);
        if (index == 2 && !artistsLoaded) loadGroups(artists, false);
        View first = firstOfCurrentTab();
        if (first != null) chips.setContentNextFocusDownId(first.getId());
    }

    @Nullable
    private View firstOfCurrentTab() {
        if (chips.selected() == 0) return songs.firstRow();
        if (chips.selected() == 1) return albums.firstCard();
        return artists.firstCard();
    }

    private void loadSongs() {
        songsLoaded = true;
        showStatus("正在载入曲库…");
        io.execute(() -> {
            List<TvApi.Track> loaded = null;
            String failure = null;
            try {
                loaded = api.allTracks(500);
            } catch (IOException error) {
                failure = error.getMessage();
            }
            final List<TvApi.Track> result = loaded;
            final String error = failure;
            post(() -> {
                if (result == null) {
                    showStatus("曲库载入失败\n" + orEmpty(error));
                    return;
                }
                status.setVisibility(GONE);
                songs.setTracks(result);
                if (chips.selected() == 0) {
                    songs.focusFirst();
                    View first = songs.firstRow();
                    if (first != null) chips.setContentNextFocusDownId(first.getId());
                }
            });
        });
    }

    private void loadGroups(final TvCardGrid grid, final boolean albumTab) {
        if (albumTab) albumsLoaded = true; else artistsLoaded = true;
        showStatus("正在载入…");
        io.execute(() -> {
            List<TvApi.Group> loaded = null;
            String failure = null;
            try {
                loaded = albumTab ? api.albums(300) : api.artists(300);
            } catch (IOException error) {
                failure = error.getMessage();
            }
            final List<TvApi.Group> result = loaded;
            final String error = failure;
            post(() -> {
                if (result == null) {
                    showStatus("载入失败\n" + orEmpty(error));
                    return;
                }
                status.setVisibility(GONE);
                List<TvCardItem> cards = new ArrayList<>(result.size());
                String kind = albumTab ? "album" : "artist";
                for (TvApi.Group group : result) {
                    cards.add(TvCardItem.ofGroup(kind + ":" + group.name, group.name,
                            group.subtitle, group.coverKey));
                }
                grid.setCards(cards);
                boolean current = albumTab ? chips.selected() == 1 : chips.selected() == 2;
                if (current) {
                    grid.focusFirst();
                    View first = grid.firstCard();
                    if (first != null) chips.setContentNextFocusDownId(first.getId());
                }
            });
        });
    }

    private void showStatus(String text) {
        status.setText(text);
        status.setVisibility(VISIBLE);
    }

    private static String orEmpty(@Nullable String value) {
        return value == null ? "" : value;
    }
}
