package com.fnaudio.client.tv;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * LRC reader for the television lyrics page.
 *
 * <p>The grammar matches the phone client's {@code lyrics_parse_policy.js} on
 * purpose: one line may carry several timestamps (a repeated chorus), anything
 * bracketed is metadata and is stripped, and a line without a timestamp is kept
 * as untimed text with time {@code -1} so a plain-text lyric still displays
 * instead of turning into an empty page. Untimed rows sort ahead of the timed
 * ones, which is what the stable {@code Array#sort} does on the phone.
 *
 * <p>Times are milliseconds. The phone policy builds them as
 * {@code minutes * 60 + seconds + Number("0." + fraction)}, so a one-digit
 * fraction is tenths and a three-digit one is milliseconds; the padding below
 * reproduces that exactly.
 */
final class TvLyricsParser {
    /** One displayable lyric line. {@code timeMs} is negative when untimed. */
    static final class Line {
        final long timeMs;
        final String text;

        Line(long timeMs, String text) {
            this.timeMs = timeMs;
            this.text = text;
        }
    }

    /** {@code [mm:ss]}, {@code [mm:ss.S]}, {@code [mm:ss.SS]}, {@code [mm:ss.SSS]}. */
    private static final Pattern STAMP =
            Pattern.compile("\\[(\\d{1,2}):(\\d{2})(?:\\.(\\d{1,3}))?\\]");
    /** Any bracketed token, including {@code [ti:]}-style metadata and offsets. */
    private static final Pattern BRACKETED = Pattern.compile("\\[[^\\]]*\\]");

    private TvLyricsParser() {
    }

    static List<Line> parse(String raw) {
        List<Line> rows = new ArrayList<>();
        if (raw == null || raw.isEmpty()) return rows;
        for (String line : raw.split("\r?\n")) {
            String content = BRACKETED.matcher(line).replaceAll("").trim();
            if (content.isEmpty()) continue;
            Matcher matcher = STAMP.matcher(line);
            boolean stamped = false;
            while (matcher.find()) {
                stamped = true;
                rows.add(new Line(stampMillis(matcher), content));
            }
            if (!stamped) rows.add(new Line(-1, content));
        }
        // Stable by contract: equal keys (all the untimed rows at -1) keep their
        // file order.
        Collections.sort(rows, new Comparator<Line>() {
            @Override public int compare(Line left, Line right) {
                return Long.compare(left.timeMs, right.timeMs);
            }
        });
        return rows;
    }

    private static long stampMillis(Matcher matcher) {
        long minutes = Long.parseLong(matcher.group(1));
        long seconds = Long.parseLong(matcher.group(2));
        String fraction = matcher.group(3);
        long millis = 0;
        if (fraction != null) {
            // "5" -> 500, "05" -> 50, "123" -> 123: right-pad to milliseconds.
            millis = Long.parseLong((fraction + "000").substring(0, 3));
        }
        return minutes * 60000L + seconds * 1000L + millis;
    }

    /**
     * Index of the line to light at {@code positionMs}, or {@code -1}.
     *
     * <p>A position before the first timestamp has no line yet; untimed rows are
     * skipped rather than treated as "at zero", otherwise a plain-text lyric
     * would light its first line forever.
     */
    static int indexAt(List<Line> lines, long positionMs) {
        int found = -1;
        for (int index = 0; index < lines.size(); index++) {
            long time = lines.get(index).timeMs;
            if (time < 0) continue;
            if (time > positionMs) break;
            found = index;
        }
        return found;
    }

    /** True when at least one row carries a timestamp, i.e. it can be followed. */
    static boolean hasTiming(List<Line> lines) {
        for (int index = 0; index < lines.size(); index++) {
            if (lines.get(index).timeMs >= 0) return true;
        }
        return false;
    }
}
