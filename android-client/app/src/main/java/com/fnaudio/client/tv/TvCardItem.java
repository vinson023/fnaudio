package com.fnaudio.client.tv;

import androidx.annotation.Nullable;

import java.util.Collections;
import java.util.List;

/**
 * One bindable card in a shelf.
 *
 * <p>Cards are either a track, a group (album/artist row), or the "continue
 * playing" shortcut that carries a playback progress. Keeping the payload on
 * the card means a click handler never has to look the item up again by id.
 */
final class TvCardItem {
    final String id;
    final String title;
    final String subtitle;
    final String coverKey;
    /** Draws the progress strip and the "继续播放" badge. */
    final boolean continueCard;
    /** 0-100, only read when {@link #continueCard} is true. */
    final int progressPercent;
    /** Track opened when the card is clicked, or null for a group card. */
    @Nullable final TvApi.Track track;
    /** Queue installed when the card is played; empty for group cards. */
    final List<TvApi.Track> queue;

    private TvCardItem(String id, String title, String subtitle, String coverKey,
                       boolean continueCard, int progressPercent,
                       @Nullable TvApi.Track track, List<TvApi.Track> queue) {
        this.id = id;
        this.title = title;
        this.subtitle = subtitle == null ? "" : subtitle;
        this.coverKey = coverKey == null ? "" : coverKey;
        this.continueCard = continueCard;
        this.progressPercent = progressPercent;
        this.track = track;
        this.queue = queue == null ? Collections.emptyList() : queue;
    }

    static TvCardItem ofGroup(String id, String title, String subtitle, String coverKey) {
        return new TvCardItem(id, title, subtitle, coverKey, false, 0, null,
                Collections.emptyList());
    }

    static TvCardItem ofTrack(TvApi.Track track, List<TvApi.Track> queue) {
        return new TvCardItem(track.id, track.title,
                track.artist + (track.format.isEmpty() ? "" : " · " + track.format),
                track.coverKey, false, 0, track, queue);
    }

    static TvCardItem ofContinue(TvApi.Track track, List<TvApi.Track> queue, int percent) {
        int clamped = Math.max(1, Math.min(99, percent));
        long played = track.durationMs * clamped / 100;
        String elapsed = TvApi.formatDuration(played);
        String total = TvApi.formatDuration(track.durationMs);
        return new TvCardItem(track.id, track.title,
                "已播 " + (elapsed == null ? "0:00" : elapsed)
                        + " / " + (total == null ? "0:00" : total),
                track.coverKey, true, clamped, track, queue);
    }
}
