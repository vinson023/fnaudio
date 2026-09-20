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
        void onRemoteCommand(String action, @Nullable Long positionMs, @Nullable String trackId, long requestToken);
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
    private int requestedRepeatMode = Player.REPEAT_MODE_OFF;
    private boolean requestedShuffle;
    @Nullable private Boolean pendingPlayWhenReady;
    private boolean pendingStop;
    @Nullable private Integer pendingRepeatMode;
    @Nullable private Boolean pendingShuffle;
    @Nullable private Integer pendingSeekIndex;
    @Nullable private Long pendingSeekPositionMs;
    private long nextRequestToken;
    private long pendingPlayToken;
    private long pendingStopToken;
    private long pendingRepeatToken;
    private long pendingShuffleToken;
    private long pendingSeekToken;

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
        currentDurationMs = safeDuration(durationMs);
        this.positionMs = safePosition(positionMs, currentDurationMs);
        this.playing = playing;
        this.repeatMode = safeRepeatMode(repeatMode);
        this.shuffle = shuffle;
        this.requestedRepeatMode = this.repeatMode;
        this.requestedShuffle = shuffle;
        this.pendingPlayWhenReady = null;
        this.pendingStop = false;
        this.pendingRepeatMode = null;
        this.pendingShuffle = null;
        this.pendingSeekIndex = null;
        this.pendingSeekPositionMs = null;
        active = !playlist.isEmpty();
        invalidateState();
    }

    public void updateStatus(int index, long positionMs, long durationMs, boolean playing) {
        verifyApplicationThread();
        if (!active) return;
        currentIndex = safeIndex(index);
        currentDurationMs = safeDuration(durationMs);
        long incomingPositionMs = safePosition(positionMs, currentDurationMs);
        if (pendingSeekIndex != null) {
            boolean targetIndexReached = currentIndex == pendingSeekIndex;
            boolean targetPositionReached = pendingSeekPositionMs == null
                    || Math.abs(incomingPositionMs - pendingSeekPositionMs) <= 1500L;
            if (targetIndexReached && targetPositionReached) {
                pendingSeekIndex = null;
                pendingSeekPositionMs = null;
            } else {
                currentIndex = Math.max(0, Math.min(pendingSeekIndex, playlist.size() - 1));
                incomingPositionMs = safePosition(
                        pendingSeekPositionMs == null ? 0L : pendingSeekPositionMs,
                        currentDurationMs
                );
            }
        }
        this.positionMs = incomingPositionMs;
        this.playing = playing;
        if (pendingPlayWhenReady != null && pendingPlayWhenReady == playing) pendingPlayWhenReady = null;
        invalidateState();
    }

    public void deactivate() {
        verifyApplicationThread();
        active = false;
        pendingPlayWhenReady = null;
        pendingStop = false;
        pendingRepeatMode = null;
        pendingShuffle = null;
        pendingSeekIndex = null;
        pendingSeekPositionMs = null;
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

    public int getRequestedRepeatMode() {
        return requestedRepeatMode;
    }

    public boolean isRequestedShuffleEnabled() {
        return requestedShuffle;
    }

    public void updateModes(int repeatMode, boolean shuffle) {
        verifyApplicationThread();
        this.repeatMode = safeRepeatMode(repeatMode);
        this.shuffle = shuffle;
        // An SSE/poll snapshot can have been produced before the user's
        // command reached the output. Keep the requested values until the
        // backend confirms them, so a retry cannot accidentally send stale
        // repeat/shuffle settings back to the server.
        if (pendingRepeatMode != null && pendingRepeatMode == this.repeatMode) {
            pendingRepeatMode = null;
        }
        if (pendingRepeatMode == null) requestedRepeatMode = this.repeatMode;
        if (pendingShuffle != null && pendingShuffle == shuffle) {
            pendingShuffle = null;
        }
        if (pendingShuffle == null) requestedShuffle = shuffle;
        invalidateState();
    }

    public void clearPendingCommand(String action, long requestToken) {
        verifyApplicationThread();
        if (("play".equals(action) || "pause".equals(action)) && pendingPlayToken == requestToken) pendingPlayWhenReady = null;
        else if ("stop".equals(action) && pendingStopToken == requestToken) pendingStop = false;
        else if ("repeat".equals(action) && pendingRepeatToken == requestToken) pendingRepeatMode = null;
        else if ("shuffle".equals(action) && pendingShuffleToken == requestToken) pendingShuffle = null;
        else if ("seek".equals(action) || "load".equals(action)) {
            if (pendingSeekToken == requestToken) {
                pendingSeekIndex = null;
                pendingSeekPositionMs = null;
            }
        }
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
        // The backend is authoritative. Do not optimistically mutate the
        // MediaSession state before its command response/SSE snapshot arrives.
        if (pendingPlayWhenReady != null && pendingPlayWhenReady == playWhenReady) {
            return Futures.immediateVoidFuture();
        }
        pendingPlayWhenReady = playWhenReady;
        pendingPlayToken = nextToken();
        commandHandler.onRemoteCommand(playWhenReady ? "play" : "pause", null, null, pendingPlayToken);
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handlePrepare() {
        if (pendingPlayWhenReady != null && pendingPlayWhenReady) {
            return Futures.immediateVoidFuture();
        }
        pendingPlayWhenReady = true;
        pendingPlayToken = nextToken();
        commandHandler.onRemoteCommand("play", null, null, pendingPlayToken);
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleStop() {
        if (pendingStop) return Futures.immediateVoidFuture();
        pendingStop = true;
        pendingPlayWhenReady = null;
        // A stop supersedes an in-flight seek/load. Keeping that projection
        // alive would make the next authoritative stopped snapshot appear at
        // the old seek target until another status update arrives.
        pendingSeekIndex = null;
        pendingSeekPositionMs = null;
        pendingStopToken = nextToken();
        commandHandler.onRemoteCommand("stop", null, null, pendingStopToken);
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleSeek(int mediaItemIndex, long positionMs, int seekCommand) {
        if (!active || playlist.isEmpty()) return Futures.immediateVoidFuture();
        int nextIndex = safeIndex(mediaItemIndex);
        pendingSeekIndex = nextIndex;
        pendingSeekPositionMs = Math.max(0L, positionMs);
        pendingSeekToken = nextToken();
        if (nextIndex != currentIndex) {
            // Media3 can seek directly to any queue item. Sending only one
            // next/previous command would land on the wrong item when the
            // requested index is more than one position away.
            commandHandler.onRemoteCommand("load", Math.max(0L, positionMs), playlist.get(nextIndex).mediaId, pendingSeekToken);
        } else {
            commandHandler.onRemoteCommand("seek", Math.max(0L, positionMs), null, pendingSeekToken);
        }
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleSetRepeatMode(int repeatMode) {
        repeatMode = safeRepeatMode(repeatMode);
        if (pendingRepeatMode != null && pendingRepeatMode == repeatMode) {
            return Futures.immediateVoidFuture();
        }
        pendingRepeatMode = repeatMode;
        requestedRepeatMode = repeatMode;
        pendingRepeatToken = nextToken();
        commandHandler.onRemoteCommand("repeat", null, null, pendingRepeatToken);
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleSetShuffleModeEnabled(boolean shuffleModeEnabled) {
        if (pendingShuffle != null && pendingShuffle == shuffleModeEnabled) {
            return Futures.immediateVoidFuture();
        }
        pendingShuffle = shuffleModeEnabled;
        requestedShuffle = shuffleModeEnabled;
        pendingShuffleToken = nextToken();
        commandHandler.onRemoteCommand("shuffle", null, null, pendingShuffleToken);
        return Futures.immediateVoidFuture();
    }

    @Override
    protected ListenableFuture<?> handleRelease() {
        // MediaSession releases this player when the service is torn down. It is
        // a local lifecycle event and must not send a remote playback command.
        active = false;
        playing = false;
        pendingPlayWhenReady = null;
        pendingStop = false;
        pendingRepeatMode = null;
        pendingShuffle = null;
        pendingSeekIndex = null;
        pendingSeekPositionMs = null;
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

    private static int safeRepeatMode(int mode) {
        return mode == Player.REPEAT_MODE_ONE || mode == Player.REPEAT_MODE_ALL
                ? mode : Player.REPEAT_MODE_OFF;
    }

    private static long safeDuration(long value) {
        return value <= 0L ? 0L : Math.min(value, 24L * 60L * 60L * 1000L);
    }

    private static long safePosition(long value, long duration) {
        long position = Math.max(0L, value);
        return duration > 0L ? Math.min(position, duration) : position;
    }

    private long nextToken() {
        nextRequestToken = nextRequestToken >= Long.MAX_VALUE - 1L ? 1L : nextRequestToken + 1L;
        return nextRequestToken;
    }
}
