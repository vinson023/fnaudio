package com.fnaudio.client.playback;

/**
 * What a "next"/"previous" press means once the queue edge is reached.
 *
 * <p>The host player cannot answer this: ExoPlayer stays on the last item when
 * {@code hasNextMediaItem()} is false, so a press looked like "replay the last
 * song" and the transport row kept claiming playback. The same rules the server
 * applies in {@code playback/core.py::next_track} live here, free of Android
 * types so they can be unit-tested on the JVM.
 */
public final class NavigationDecision {

    public enum Move {
        /** Move to the neighbouring item. */
        STEP,
        /** Repeat-all at the end: continue at the other end of the queue. */
        WRAP,
        /** Repeat-one: restart the item that is already loaded. */
        REPLAY,
        /** Repeat-off at the edge: nothing to play, the page stops. */
        NONE
    }

    private NavigationDecision() {
    }

    public static Move next(int size, int index, boolean repeatAll, boolean repeatOne) {
        if (size <= 0 || index < 0) return Move.NONE;
        if (repeatOne) return Move.REPLAY;
        if (index < size - 1) return Move.STEP;
        return repeatAll ? Move.WRAP : Move.NONE;
    }

    public static Move previous(int size, int index, boolean repeatAll, boolean repeatOne) {
        if (size <= 0 || index < 0) return Move.NONE;
        if (repeatOne) return Move.REPLAY;
        if (index > 0) return Move.STEP;
        return repeatAll ? Move.WRAP : Move.NONE;
    }
}
