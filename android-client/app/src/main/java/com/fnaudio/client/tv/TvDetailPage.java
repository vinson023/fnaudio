package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
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

import androidx.annotation.Nullable;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;

/**
 * Album, artist and playlist detail: one header, one track list.
 *
 * <p>The three pages differ only in how the tracks are resolved - an album name,
 * an artist name, or a saved playlist's ids - so they share this view and it
 * asks the right question based on the card id it is handed. Keeping them
 * together also means the back path, the play-all button and the empty state
 * are implemented once.
 */
final class TvDetailPage extends FrameLayout {
    interface OnPlay {
        void onPlay(TvApi.Track track, int index, List<TvApi.Track> queue);
    }

    private final TvApi api;
    private final TvArtworkLoader artwork;
    private final ExecutorService io;
    private final FrameLayout coverBox;
    private final ImageView cover;
    private final TextView kind;
    private final TextView title;
    private final TextView subtitle;
    private final TextView playAll;
    private final TvTrackList list;

    @Nullable private OnPlay playListener;
    @Nullable private Runnable backListener;
    private List<TvApi.Track> tracks = Collections.emptyList();
    private int token;

    TvDetailPage(Context context, TvApi api, TvArtworkLoader artwork, ExecutorService io) {
        super(context);
        this.api = api;
        this.artwork = artwork;
        this.io = io;
        setBackgroundColor(TvTheme.BG);
        setVisibility(GONE);

        LinearLayout column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        addView(column, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout header = new LinearLayout(context);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(TvTheme.dp(context, TvTheme.SCREEN_EDGE),
                TvTheme.dp(context, 16), TvTheme.dp(context, TvTheme.SCREEN_EDGE),
                TvTheme.dp(context, 12));
        column.addView(header, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        coverBox = new FrameLayout(context);
        coverBox.setBackground(TvTheme.rounded(context, 0xFF14161F, 10f));
        TvUi.roundClip(coverBox, 10f);
        header.addView(coverBox, new LinearLayout.LayoutParams(
                TvTheme.dp(context, 132), TvTheme.dp(context, 132)));

        cover = new ImageView(context);
        cover.setScaleType(ImageView.ScaleType.CENTER_CROP);
        coverBox.addView(cover, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout info = new LinearLayout(context);
        info.setOrientation(LinearLayout.VERTICAL);
        info.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams infoParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        infoParams.leftMargin = TvTheme.dp(context, 24);
        header.addView(info, infoParams);

        kind = new TextView(context);
        kind.setTextColor(TvTheme.ACCENT);
        kind.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_META);
        kind.setLetterSpacing(0.1f);
        info.addView(kind);

        title = new TextView(context);
        title.setTextColor(TvTheme.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 28f);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        titleParams.topMargin = TvTheme.dp(context, 4);
        info.addView(title, titleParams);

        subtitle = new TextView(context);
        subtitle.setTextColor(TvTheme.TEXT_3);
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_SUB);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(TextUtils.TruncateAt.END);
        info.addView(subtitle);

        playAll = new TextView(context);
        playAll.setText("播放全部");
        playAll.setTextColor(TvTheme.TEXT);
        playAll.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_SUB);
        playAll.setGravity(Gravity.CENTER);
        playAll.setSingleLine(true);
        playAll.setFocusable(true);
        playAll.setFocusableInTouchMode(false);
        playAll.setPadding(TvTheme.dp(context, 20), TvTheme.dp(context, 9),
                TvTheme.dp(context, 20), TvTheme.dp(context, 9));
        playAll.setBackground(TvTheme.cardBackground(context, TvTheme.R_PILL));
        playAll.setForeground(TvTheme.focusRing(context, TvTheme.R_PILL));
        playAll.setOnClickListener(view -> {
            if (playListener == null || tracks.isEmpty()) return;
            playListener.onPlay(tracks.get(0), 0, tracks);
        });
        playAll.setOnFocusChangeListener((view, hasFocus) -> view.animate()
                .scaleX(hasFocus ? 1.05f : 1f).scaleY(hasFocus ? 1.05f : 1f)
                .setDuration(TvTheme.FOCUS_MS).start());
        header.addView(playAll);

        list = new TvTrackList(context);
        list.setEmptyText("这张专辑里还没有歌曲");
        list.setOnPick((track, index, queue) -> {
            if (playListener != null) playListener.onPlay(track, index, queue);
        });
        list.setOnTopEdge(() -> playAll.requestFocus());
        column.addView(list, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        playAll.setNextFocusDownId(0);
    }

    void setOnPlay(OnPlay value) {
        this.playListener = value;
    }

    void setOnBack(Runnable value) {
        this.backListener = value;
    }

    /**
     * Loads the page for a card id.
     *
     * <p>{@code album:} and {@code artist:} carry the name; {@code playlist:}
     * carries the saved id, which has to be looked up in the account state
     * because a playlist is only a list of track ids.
     */
    void open(String kindId) {
        final int request = ++token;
        setVisibility(VISIBLE);
        cover.setImageDrawable(null);
        kind.setText(kindLabel(kindId));
        title.setText(nameOf(kindId));
        subtitle.setText("正在载入…");
        list.setTracks(new ArrayList<>());
        playAll.requestFocus();

        io.execute(() -> {
            List<TvApi.Track> loaded = null;
            String failure = null;
            try {
                loaded = resolve(kindId);
            } catch (IOException error) {
                failure = error.getMessage();
            }
            final List<TvApi.Track> result = loaded;
            final String error = failure;
            post(() -> {
                if (request != token) return;
                if (result == null) {
                    subtitle.setText("载入失败\n" + (error == null ? "" : error));
                    return;
                }
                tracks = result;
                subtitle.setText(result.size() + " 首");
                list.setTracks(result);
                if (!result.isEmpty() && result.get(0).hasCover()) {
                    artwork.load(result.get(0).coverKey, cover);
                }
                playAll.setNextFocusDownId(list.firstRow() == null ? 0 : list.firstRow().getId());
            });
        });
    }

    private List<TvApi.Track> resolve(String kindId) throws IOException {
        if (kindId.startsWith("album:")) {
            return api.albumTracks(kindId.substring("album:".length()), 500);
        }
        if (kindId.startsWith("artist:")) {
            return api.artistTracks(kindId.substring("artist:".length()), 500);
        }
        if (kindId.startsWith("playlist:")) {
            String id = kindId.substring("playlist:".length());
            TvApi.UserState state = api.userState();
            for (TvApi.Playlist playlist : state.playlists) {
                if (playlist.id.equals(id)) {
                    if (playlist.trackIds.isEmpty()) return new ArrayList<>();
                    return api.tracksByIds(new ArrayList<>(playlist.trackIds));
                }
            }
            return new ArrayList<>();
        }
        return new ArrayList<>();
    }

    private static String kindLabel(String kindId) {
        if (kindId.startsWith("album:")) return "专辑";
        if (kindId.startsWith("artist:")) return "艺术家";
        if (kindId.startsWith("playlist:")) return "播放列表";
        return "";
    }

    private static String nameOf(String kindId) {
        int colon = kindId.indexOf(':');
        return colon < 0 ? kindId : kindId.substring(colon + 1);
    }

    /** The list is loaded after the page opens, so the header owns first focus. */
    void focusFirst() {
        playAll.requestFocus();
    }

    boolean handleKey(int keyCode, KeyEvent event) {
        if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
        if (keyCode != KeyEvent.KEYCODE_BACK) return false;
        if (backListener != null) backListener.run();
        return true;
    }
}
