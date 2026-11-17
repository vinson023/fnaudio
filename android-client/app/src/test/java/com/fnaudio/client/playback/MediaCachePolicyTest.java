package com.fnaudio.client.playback;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** P2-2：缓存规则的表。断网可放靠它，别让人悄悄把碎片也缓存进去。 */
public class MediaCachePolicyTest {

    @Test
    public void wholeTrackRequestsAreCacheable() {
        assertTrue(MediaCachePolicy.shouldCache("http://nas/media?id=abc"));
        assertTrue(MediaCachePolicy.shouldCache("http://nas/media?id=abc&transcode=mp3"));
        assertTrue(MediaCachePolicy.shouldCache("http://nas/media?id=abc&transcode=mp3&start=0"));
    }

    @Test
    public void midTrackRequestsAreNot() {
        assertFalse(MediaCachePolicy.shouldCache("http://nas/media?id=abc&transcode=mp3&start=12.5"));
        assertFalse(MediaCachePolicy.shouldCache("http://nas/media?id=abc&start=3"));
        assertFalse(MediaCachePolicy.shouldCache("http://nas/media?id=abc&start=abc"));
        // 空的 start= 等于没给偏移，按整段处理
        assertTrue(MediaCachePolicy.shouldCache("http://nas/media?id=abc&start="));
    }

    @Test
    public void startInTheMiddleOfTheQueryIsStillSeen() {
        assertFalse(MediaCachePolicy.shouldCache("http://nas/media?start=90&id=abc"));
        assertTrue(MediaCachePolicy.shouldCache("http://nas/media?restart=1&id=abc"));
    }

    @Test
    public void emptyInputIsNotCacheable() {
        assertFalse(MediaCachePolicy.shouldCache(null));
        assertFalse(MediaCachePolicy.shouldCache(""));
    }

    @Test
    public void theBudgetIsClamped() {
        assertEquals(0, MediaCachePolicy.clampMaxBytes(0));
        assertEquals(0, MediaCachePolicy.clampMaxBytes(-5));
        assertEquals(MediaCachePolicy.DEFAULT_MAX_BYTES, MediaCachePolicy.clampMaxBytes(MediaCachePolicy.DEFAULT_MAX_BYTES));
        assertEquals(MediaCachePolicy.MAX_MAX_BYTES, MediaCachePolicy.clampMaxBytes(Long.MAX_VALUE));
    }
}
