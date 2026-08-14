package com.fnaudio.client.playback;

import android.os.Looper;

import androidx.annotation.Nullable;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.media3.common.SimpleBasePlayer;
import androidx.media3.common.util.UnstableApi;

import com.google.common.collect.ImmutableList;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * A Media3 player that mirrors playback owned by a remote fnAudio output.
 *
 * <p>No media is downloaded or decoded on the phone. The player only exposes
 * remote metadata/state to MediaSession and forwards transport commands to the
 * server-side output.</p>
 */
@androidx.annotation.OptIn(markerClass = UnstableApi.class)
public final class RemotePlaybackPlayer extends SimpleBasePlayer {
    public interface CommandHandler {
        void onRemoteCommand(String action, @Nullable Long positionMs);
    }

    private static final Player.Commands COMMANDS = new Player.Commands.Builder()
            .addAll(
                    Player.COMMAND_PLAY_PAUSE,
                    Player.COMMAND_PREPARE,
                    Player.COMMAND_STOP,
                    Player.COMMAND_SEEK_IN_CURRENT_MEDIA_ITEM,
                    Player.COMMAND_SEEK_TO_MEDIA_ITEM,
                    Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM,
                    Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM,
                    Player.COMMAND_GET_CURRENT_MEDIA_ITEM,
                    Player.COMMAND_GET_TIMELINE,
                    Player.COMMAND_GET_MEDIA_ITEMS_METADATA,
                    Player.COMMAND_SET_REPEAT_MODE,
                    Player.COMMAND_SET_SHUFFLE_MODE,
                    Player.COMMAND_RELEASE
            )
            .build();

    private final CommandHandler commandHandler;
    private List<MediaItem> playlist = Collections.emptyList();
    private int currentIndex;
    private long positionMs;
    private long currentDurationMs;
    private boolean active;
    private boolean playing;
    private int repeatMode = Player.REPEAT_MODE_OFF;
    private boolean shuffle;

    public RemotePlaybackPlayer(Looper looper, CommandHandler commandHandler) {
        super(looper);
        this.commandHandler = commandHandler;
    }

    public void activate(
            List<MediaItem> items,
            int index,
            long positionMs,
            long durationMs,
            boolean playing,
            int repeatMode,
            boolean shuffle
    ) {
        verifyApplicationThread();
        playlist = Collections.unmodifiableList(new ArrayList<>(items));
        currentIndex = safeIndex(index);
        this.positionMs = Math.max(0L, positionMs);
        currentDurationMs = Math.max(0L, durationMs);
        this.playing = playing;
        this.repeatMode = repeatMode;
        this.shuffle = shuffle;
        active = !playlist.isEmpty();
        invalidateState();
    }

    public void updateStatus(int index, long positionMs, long durationMs, boolean playing) {
        verifyApplicationThread();
        if (!active) return;
        currentIndex = safeIndex(index);
        this.positionMs = Math.max(0L, positionMs);
        currentDurationMs = Math.max(0L, durationMs);
        this.playing = playing;
        invalidateState();
    }

    public void deactivate() {
        verifyApplicationThread();
        active = false;
        playing = false;
        positionMs = 0L;
        currentDurationMs = 0L;
        playlist = Collections.emptyList();
        currentIndex = 0;
        invalidateState();
    }

    public boolean isRemoteActive() {
        return active;
    }

    public boolean isRemotePlaying() {
        return active && playing;
    }

    public int getRemoteRepeatMode() {
        return repeatMode;
    }

    public boolean isRemoteShuffleEnabled() {
        return shuffle;
    }

    @Nullable
    public MediaItem currentRemoteItem() {
        return playlist.isEmpty() ? null : playlist.get(safeIndex(currentIndex));
    }

    @Override
    protected State getState() {
        ImmutableList.Builder<MediaItemData> rows = ImmutableList.builder();
        for (int i = 0; i < playlist.size(); i++) {
            MediaItem item = playlist.get(i);
            long durationMs = item.mediaMetadata.durationMs == null ? 0L : Math.max(0L, item.mediaMetadata.durationMs);
            if (i == currentIndex && currentDurationMs > 0L) durationMs = currentDurationMs;
            rows.add(new MediaItemData.Builder(item.mediaId + ":" + i)
                    .setMediaItem(item)
                    .setMediaMetadata(item.mediaMetadata)
                    .setIsSeekable(durationMs > 0L)
                    .setDurationUs(durationMs > 0L ? durationMs * 1000L : C.TIME_UNSET)
                    .build());
        }
        PositionSupplier position = playing
                ? PositionSupplier.getExtrapolating(positionMs, 1f)
                : PositionSupplier.getConstant(positionMs);
        return new State.Builder()
                .setAvailableCommands(active ? COMMANDS : Player.Commands.EMPTY)
                .setPlaylist(rows.build())
                .setCurrentMediaItemIndex(playlist.isEmpty() ? 0 : safeIndex(currentIndex))
                .setContentPositionMs(position)
                .setContentBufferedPositionMs(position)
                .setPlayWhenReady(playing, Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST)
                .setPlaybackState(active ? Player.STATE_READY : Player.STATE_IDLE)
                .setRepeatMode(repeatMode)
                .setShuffleModeEnabled(shuffle)
                .build();
    }

    @Override
    protected ListenableFuture<?> handleSetPlayWhenReady(boolean playWhenReady) {
        playing = playWhenReady;
        commandHandler.onRemoteCommand(playWhenReady ? "play" : "pause", null);
        invalidateState();
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handlePrepare() {
        commandHandler.onRemoteCommand("play", null);
        playing = true;
        invalidateState();
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleStop() {
        commandHandler.onRemoteCommand("stop", null);
        playing = false;
        positionMs = 0L;
        invalidateState();
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleSeek(int mediaItemIndex, long positionMs, int seekCommand) {
        int nextIndex = safeIndex(mediaItemIndex);
        if (nextIndex != currentIndex) {
            String action = nextIndex > currentIndex ? "next" : "previous";
            currentIndex = nextIndex;
            this.positionMs = 0L;
            commandHandler.onRemoteCommand(action, null);
        } else {
            this.positionMs = Math.max(0L, positionMs);
            commandHandler.onRemoteCommand("seek", this.positionMs);
        }
        invalidateState();
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleSetRepeatMode(int repeatMode) {
        this.repeatMode = repeatMode;
        commandHandler.onRemoteCommand("repeat", null);
        invalidateState();
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleSetShuffleModeEnabled(boolean shuffleModeEnabled) {
        shuffle = shuffleModeEnabled;
        commandHandler.onRemoteCommand("shuffle", null);
        invalidateState();
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleRelease() {
        // MediaSession releases this player when the service is torn down. It is
        // a local lifecycle event and must not send a remote playback command.
        active = false;
        playing = false;
        playlist = Collections.emptyList();
        currentIndex = 0;
        positionMs = 0L;
        currentDurationMs = 0L;
        invalidateState();
        return Futures.immediateVoidFuture();
    }

    private int safeIndex(int index) {
        if (playlist.isEmpty()) return 0;
        return Math.max(0, Math.min(index, playlist.size() - 1));
    }
}
