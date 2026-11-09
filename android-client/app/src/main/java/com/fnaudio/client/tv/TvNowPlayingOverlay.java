package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.annotation.Nullable;

import java.util.ArrayList;
import java.util.List;

/**
 * Full-screen now-playing surface.
 *
 * <p>Layout follows what the streaming services settled on for televisions: the
 * cover and transport controls own the left half, and "up next" occupies the
 * right half so the viewer can see what follows without leaving the screen.
 * D-pad left and right seek, up enters the queue, and Back returns to browsing.
 */
final class TvNowPlayingOverlay extends FrameLayout {
    private final TvPlayer player;
    private final TextView title;
    private final TextView subtitle;
    private final ProgressBar seek;
    private final TextView elapsed;
    private final TextView total;
    private final TextView playButton;
    private final TextView shuffleButton;
    private final TextView repeatButton;
    private final ImageView cover;
    private final ImageView backdrop;
    private final TvTrackListView queueList;
    private final TvArtworkLoader artwork;

    @Nullable private Runnable onClose;
    private long durationMs;

    TvNowPlayingOverlay(Context context, TvPlayer player, TvArtworkLoader artwork) {
        super(context);
        this.player = player;
        this.artwork = artwork;
        setBackgroundColor(TvUi.BG);
        setFocusable(false);

        backdrop = new ImageView(context);
        backdrop.setScaleType(ImageView.ScaleType.CENTER_CROP);
        backdrop.setAlpha(0.30f);
        addView(backdrop, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        GradientDrawable veil = new GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{0xF207080A, 0xE607080A, 0xFA07080A});
        addView(new View(context) {{
            setBackground(veil);
        }}, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout body = new LinearLayout(context);
        body.setOrientation(LinearLayout.HORIZONTAL);
        body.setPadding(TvUi.dp(context, 36), TvUi.dp(context, 28),
                TvUi.dp(context, 28), TvUi.dp(context, 18));
        addView(body, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout left = new LinearLayout(context);
        left.setOrientation(LinearLayout.VERTICAL);
        body.addView(left, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 1.1f));

        cover = new ImageView(context);
        cover.setScaleType(ImageView.ScaleType.CENTER_CROP);
        TvUi.roundClip(cover, 16f);
        LinearLayout.LayoutParams coverParams = new LinearLayout.LayoutParams(
                TvUi.dp(context, 196), TvUi.dp(context, 196));
        left.addView(cover, coverParams);

        title = new TextView(context);
        title.setTextColor(TvUi.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        title.setSingleLine(true);
        title.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        titleParams.topMargin = TvUi.dp(context, 20);
        left.addView(title, titleParams);

        subtitle = new TextView(context);
        subtitle.setTextColor(TvUi.TEXT_2);
        subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f);
        subtitle.setSingleLine(true);
        subtitle.setEllipsize(TextUtils.TruncateAt.END);
        left.addView(subtitle);

        LinearLayout seekRow = new LinearLayout(context);
        seekRow.setOrientation(LinearLayout.HORIZONTAL);
        seekRow.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams seekRowParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        seekRowParams.topMargin = TvUi.dp(context, 22);
        left.addView(seekRow, seekRowParams);

        elapsed = timeLabel(context);
        seekRow.addView(elapsed);

        seek = new ProgressBar(context, null, android.R.attr.progressBarStyleHorizontal);
        seek.setMax(1000);
        seek.setProgressTintList(android.content.res.ColorStateList.valueOf(Color.WHITE));
        seek.setProgressBackgroundTintList(
                android.content.res.ColorStateList.valueOf(0x4DFFFFFF));
        LinearLayout.LayoutParams seekParams = new LinearLayout.LayoutParams(0,
                TvUi.dp(context, 4), 1f);
        seekParams.leftMargin = TvUi.dp(context, 12);
        seekParams.rightMargin = TvUi.dp(context, 12);
        seekRow.addView(seek, seekParams);

        total = timeLabel(context);
        seekRow.addView(total);

        LinearLayout controls = new LinearLayout(context);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams controlParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        controlParams.topMargin = TvUi.dp(context, 26);
        left.addView(controls, controlParams);

        TextView previous = controlButton(context, "上一首");
        previous.setOnClickListener(view -> player.previous());
        controls.addView(previous);

        playButton = controlButton(context, "播放");
        LinearLayout.LayoutParams playParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        playParams.leftMargin = TvUi.dp(context, 10);
        playParams.rightMargin = TvUi.dp(context, 10);
        playButton.setOnClickListener(view -> player.toggle());
        controls.addView(playButton, playParams);

        TextView next = controlButton(context, "下一首");
        next.setOnClickListener(view -> player.next());
        controls.addView(next);

        shuffleButton = controlButton(context, "随机");
        LinearLayout.LayoutParams shuffleParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        shuffleParams.leftMargin = TvUi.dp(context, 22);
        shuffleButton.setOnClickListener(view -> {
            player.setShuffle(!player.shuffle());
            syncToggles();
        });
        controls.addView(shuffleButton, shuffleParams);

        repeatButton = controlButton(context, "循环");
        LinearLayout.LayoutParams repeatParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        repeatParams.leftMargin = TvUi.dp(context, 8);
        repeatButton.setOnClickListener(view -> {
            player.setRepeatAll(!player.repeatAll());
            syncToggles();
        });
        controls.addView(repeatButton, repeatParams);

        // D-pad order inside the transport row, spelled out because the buttons
        // have different widths and geometric focus search picked odd targets.
        previous.setNextFocusRightId(playButton.getId());
        playButton.setNextFocusLeftId(previous.getId());
        playButton.setNextFocusRightId(next.getId());
        next.setNextFocusLeftId(playButton.getId());
        next.setNextFocusRightId(shuffleButton.getId());
        shuffleButton.setNextFocusLeftId(next.getId());
        shuffleButton.setNextFocusRightId(repeatButton.getId());
        repeatButton.setNextFocusLeftId(shuffleButton.getId());

        LinearLayout right = new LinearLayout(context);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setPadding(TvUi.dp(context, 32), 0, 0, 0);
        body.addView(right, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.MATCH_PARENT, 0.9f));

        TextView heading = new TextView(context);
        heading.setText("接下来");
        heading.setTextColor(TvUi.TEXT_2);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        heading.setLetterSpacing(0.1f);
        heading.setPadding(TvUi.dp(context, 12), 0, 0, TvUi.dp(context, 12));
        right.addView(heading);

        queueList = new TvTrackListView(context, artwork);
        queueList.setOnTrackClick((track, position) -> player.playAt(position));
        // Up enters the queue; left is the way back to the transport buttons,
        // which is the only exit a viewer is likely to guess on a remote.
        queueList.setOnLeftEdge(position -> {
            playButton.requestFocus();
            return true;
        });
        right.addView(queueList, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // Up from the transport row enters the queue, Down leaves it.
        View.OnKeyListener toQueue = (view, keyCode, event) -> {
            if (event.getAction() == KeyEvent.ACTION_DOWN
                    && keyCode == KeyEvent.KEYCODE_DPAD_UP) {
                queueList.focusFirst();
                return true;
            }
            return false;
        };
        previous.setOnKeyListener(toQueue);
        playButton.setOnKeyListener(toQueue);
        next.setOnKeyListener(toQueue);
        shuffleButton.setOnKeyListener(toQueue);
        repeatButton.setOnKeyListener(toQueue);

        syncToggles();
    }

    private TextView timeLabel(Context context) {
        TextView label = new TextView(context);
        label.setText("0:00");
        label.setTextColor(TvUi.TEXT_3);
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f);
        return label;
    }

    private TextView controlButton(Context context, String label) {
        TextView button = new TextView(context);
        button.setText(label);
        button.setId(View.generateViewId());
        button.setTextColor(TvUi.TEXT);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        button.setGravity(Gravity.CENTER);
        button.setFocusable(true);
        button.setFocusableInTouchMode(false);
        // Single line is not cosmetic here: "循环 · 开" is wider than "循环", and
        // without it the last button in the row silently split over two lines.
        button.setSingleLine(true);
        button.setMinWidth(TvUi.dp(context, 62));
        button.setPadding(TvUi.dp(context, 18), TvUi.dp(context, 11),
                TvUi.dp(context, 18), TvUi.dp(context, 11));
        // The focus ring is part of the background on these pills: as a
        // foreground it stopped being drawn once the label was set, and the
        // transport row would show no highlight at all.
        GradientDrawable idle = new GradientDrawable();
        idle.setShape(GradientDrawable.RECTANGLE);
        idle.setCornerRadius(TvUi.dp(context, 22));
        idle.setColor(0x33FFFFFF);

        GradientDrawable focused = new GradientDrawable();
        focused.setShape(GradientDrawable.RECTANGLE);
        focused.setCornerRadius(TvUi.dp(context, 22));
        focused.setColor(0x4DFFFFFF);
        focused.setStroke(Math.max(2, TvUi.dp(context, 2)), Color.WHITE);

        android.graphics.drawable.StateListDrawable states =
                new android.graphics.drawable.StateListDrawable();
        states.addState(new int[]{android.R.attr.state_focused}, focused);
        states.addState(new int[]{}, idle);
        button.setBackground(states);
        TvUi.applyFocusScale(button, 1.08f);
        return button;
    }

    private void syncToggles() {
        shuffleButton.setText(player.shuffle() ? "随机 · 开" : "随机");
        shuffleButton.setTextColor(player.shuffle() ? TvUi.ACCENT : TvUi.TEXT);
        repeatButton.setText(player.repeatAll() ? "循环 · 开" : "循环");
        repeatButton.setTextColor(player.repeatAll() ? TvUi.ACCENT : TvUi.TEXT);
    }

    void setOnClose(Runnable action) {
        this.onClose = action;
    }

    void requestInitialFocus() {
        // The overlay is materialised from GONE at this moment, so the focus
        // request is deferred one frame; asking immediately after setVisibility
        // sometimes lands on a child that is not laid out yet and the screen
        // opens with no highlight at all.
        post(() -> playButton.requestFocus());
        TvApi.Track current = player.current();
        if (current == null) {
            showEmptyState();
            return;
        }
        onTrackChanged(current);
        onPlayingChanged(player.isPlaying());
        refreshQueue();
    }

    /** Nothing has been played since the app started: say so instead of a blank page. */
    private void showEmptyState() {
        title.setText("还没有在播放");
        subtitle.setText("先挑一首歌，再回到这里");
        durationMs = 0;
        seek.setProgress(0);
        elapsed.setText("0:00");
        total.setText("0:00");
        cover.setImageDrawable(null);
        // Hiding rather than blanking the cover keeps the empty message at the
        // top of the column instead of floating under 196dp of nothing.
        cover.setVisibility(View.GONE);
        backdrop.setImageDrawable(null);
        queueList.setTracks(new ArrayList<>());
        queueList.setNowPlayingId("");
    }

    void onTrackChanged(@Nullable TvApi.Track track) {
        if (track == null) {
            showEmptyState();
            return;
        }
        title.setText(track.title);
        subtitle.setText(track.artist + (track.album.isEmpty() ? "" : " · " + track.album));
        durationMs = track.durationMs;
        cover.setVisibility(View.VISIBLE);
        artwork.load(track.coverKey, cover);
        artwork.loadHires(track.coverKey, backdrop);
        total.setText(orDash(TvApi.formatDuration(track.durationMs)));
        refreshQueue();
    }

    void onPlayingChanged(boolean playing) {
        playButton.setText(playing ? "暂停" : "播放");
    }

    void onProgress(long positionMs, long durationMs) {
        long length = durationMs > 0 ? durationMs : this.durationMs;
        seek.setProgress(length <= 0 ? 0
                : (int) Math.min(1000, Math.round(positionMs * 1000.0 / length)));
        elapsed.setText(orDash(TvApi.formatDuration(positionMs)));
        if (length > 0) total.setText(orDash(TvApi.formatDuration(length)));
    }

    private void refreshQueue() {
        List<TvApi.Track> queue = new ArrayList<>(player.queue());
        queueList.setTracks(queue);
        TvApi.Track current = player.current();
        if (current != null) queueList.setNowPlayingId(current.id);
    }

    private static String orDash(@Nullable String value) {
        return value == null ? "0:00" : value;
    }

    /** Handles remote keys while the overlay is visible. */
    boolean handleKey(int keyCode, KeyEvent event) {
        if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
        switch (keyCode) {
            case KeyEvent.KEYCODE_BACK:
                if (onClose != null) onClose.run();
                return true;
            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
            case KeyEvent.KEYCODE_MEDIA_PLAY:
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                player.toggle();
                return true;
            case KeyEvent.KEYCODE_MEDIA_NEXT:
                player.next();
                return true;
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                player.previous();
                return true;
            case KeyEvent.KEYCODE_DPAD_LEFT:
                if (isTransportFocused()) {
                    player.seekTo(Math.max(0, currentPosition() - 10000));
                    return true;
                }
                return false;
            case KeyEvent.KEYCODE_DPAD_RIGHT:
                if (isTransportFocused()) {
                    long length = durationMs > 0 ? durationMs : currentDuration();
                    player.seekTo(Math.min(Math.max(0, length - 1000),
                            currentPosition() + 10000));
                    return true;
                }
                return false;
            default:
                return false;
        }
    }

    private boolean isTransportFocused() {
        View focused = findFocus();
        return focused != null && (focused == playButton || focused == shuffleButton
                || focused == repeatButton);
    }

    private long currentPosition() {
        return player.position();
    }

    private long currentDuration() {
        long length = player.duration();
        return length > 0 ? length : durationMs;
    }
}
