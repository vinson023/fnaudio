package com.fnaudio.client.playback;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/**
 * The queue-edge table, mirrored from the server's {@code next_track()}.
 *
 * <p>This is the rule that decides whether pressing next at the last track replays
 * it (report 2026-11-17: "the last track repeats for ever").
 */
public class NavigationDecisionTest {

    @Test
    public void repeatOffStopsAtTheEnd() {
        assertEquals(NavigationDecision.Move.NONE, NavigationDecision.next(3, 2, false, false));
        assertEquals(NavigationDecision.Move.NONE, NavigationDecision.previous(3, 0, false, false));
    }

    @Test
    public void repeatOffStepsThroughTheQueue() {
        assertEquals(NavigationDecision.Move.STEP, NavigationDecision.next(3, 0, false, false));
        assertEquals(NavigationDecision.Move.STEP, NavigationDecision.next(3, 1, false, false));
        assertEquals(NavigationDecision.Move.STEP, NavigationDecision.previous(3, 2, false, false));
    }

    @Test
    public void repeatAllWrapsInBothDirections() {
        assertEquals(NavigationDecision.Move.WRAP, NavigationDecision.next(3, 2, true, false));
        assertEquals(NavigationDecision.Move.WRAP, NavigationDecision.previous(3, 0, true, false));
        assertEquals(NavigationDecision.Move.STEP, NavigationDecision.next(3, 0, true, false));
    }

    @Test
    public void repeatOneReplaysTheCurrentTrack() {
        assertEquals(NavigationDecision.Move.REPLAY, NavigationDecision.next(3, 2, false, true));
        assertEquals(NavigationDecision.Move.REPLAY, NavigationDecision.next(3, 0, false, true));
        assertEquals(NavigationDecision.Move.REPLAY, NavigationDecision.previous(3, 0, false, true));
        // "one" wins over "all" if both somehow arrive, like the server's branch order.
        assertEquals(NavigationDecision.Move.REPLAY, NavigationDecision.next(3, 2, true, true));
    }

    @Test
    public void singleItemQueueBehavesLikeTheServer() {
        assertEquals(NavigationDecision.Move.NONE, NavigationDecision.next(1, 0, false, false));
        assertEquals(NavigationDecision.Move.WRAP, NavigationDecision.next(1, 0, true, false));
        assertEquals(NavigationDecision.Move.REPLAY, NavigationDecision.next(1, 0, false, true));
    }

    @Test
    public void anEmptyQueueOrMissingIndexHasNowhereToGo() {
        assertEquals(NavigationDecision.Move.NONE, NavigationDecision.next(0, 0, true, false));
        assertEquals(NavigationDecision.Move.NONE, NavigationDecision.previous(0, 0, true, false));
        assertEquals(NavigationDecision.Move.NONE, NavigationDecision.next(3, -1, true, true));
    }
}
