package com.fnaudio.client.tv;

import android.content.Context;

import androidx.annotation.Nullable;

import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.network.HttpClientFactory;
import com.fnaudio.client.network.SessionCookies;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

import okhttp3.HttpUrl;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * Read-only gateway to the fnAudio CGI from the TV client.
 *
 * <p>The phone client drives playback through a MediaSessionService because it
 * has to survive the WebView being backgrounded. A television has no such
 * requirement: it stays on one screen, so the TV client plays locally through
 * {@link TvPlayer} and only needs the library read routes below.
 *
 * <p>Every call here is synchronous and must run off the main thread. The
 * routes are the same ones the bundled WebView uses, so an authenticated
 * profile that works for the phone works for the TV without a second login.
 */
public final class TvApi {
    /** One library row, projected into only the fields a ten-foot UI draws. */
    public static final class Track {
        public final String id;
        public final String title;
        public final String artist;
        public final String album;
        public final long durationMs;
        public final String format;
        public final int trackNo;
        public final String coverKey;

        Track(String id, String title, String artist, String album, long durationMs,
              String format, int trackNo, String coverKey) {
            this.id = id;
            this.title = title;
            this.artist = artist;
            this.album = album;
            this.durationMs = durationMs;
            this.format = format;
            this.trackNo = trackNo;
            this.coverKey = coverKey;
        }

        boolean hasCover() {
            return coverKey != null && !coverKey.isEmpty();
        }
    }

    /** An album or artist grouping row from {@code /api/library/groups}. */
    public static final class Group {
        public final String name;
        public final String subtitle;
        public final int trackCount;
        public final String coverKey;

        Group(String name, String subtitle, int trackCount, String coverKey) {
            this.name = name;
            this.subtitle = subtitle;
            this.trackCount = trackCount;
            this.coverKey = coverKey;
        }
    }

    private static final int PAGE_LIMIT_MAX = 500;

    private final Context context;
    private final ConnectionProfile profile;
    private final OkHttpClient client;

    public TvApi(Context context, ConnectionProfile profile) {
        this.context = context.getApplicationContext();
        this.profile = profile;
        this.client = HttpClientFactory.create(this.context, profile);
    }

    public String profileLabel() {
        return profile.name == null || profile.name.isEmpty() ? profile.host : profile.name;
    }

    /** The authenticated connection this client is bound to. */
    public ConnectionProfile profile() {
        return profile;
    }

    // ---------------------------------------------------------------- library

    /** Newest tracks first. The home hero uses the first row of this shelf. */
    public List<Track> recentTracks(int limit) throws IOException {
        return parseTracks(request("api/library?paged=1&view=recent&sort=added&dir=desc&limit="
                + clampLimit(limit)));
    }

    /** The whole library, alphabetical. This is the "tracks" browse page. */
    public List<Track> allTracks(int limit) throws IOException {
        return parseTracks(request("api/library?paged=1&view=all&sort=title&dir=asc&limit="
                + clampLimit(limit)));
    }

    /** Tracks of one album, in disc order. */
    public List<Track> albumTracks(String album, int limit) throws IOException {
        HttpUrl url = baseBuilder("api/library").addQueryParameter("paged", "1")
                .addQueryParameter("view", "all")
                .addQueryParameter("album", album == null ? "" : album)
                .addQueryParameter("sort", "track_no")
                .addQueryParameter("dir", "asc")
                .addQueryParameter("limit", String.valueOf(clampLimit(limit)))
                .build();
        return parseTracks(request(url));
    }

    /** Tracks credited to one artist, album then disc order. */
    public List<Track> artistTracks(String artist, int limit) throws IOException {
        HttpUrl url = baseBuilder("api/library").addQueryParameter("paged", "1")
                .addQueryParameter("view", "all")
                .addQueryParameter("search", artist == null ? "" : artist)
                .addQueryParameter("sort", "album")
                .addQueryParameter("dir", "asc")
                .addQueryParameter("limit", String.valueOf(clampLimit(limit)))
                .build();
        return parseTracks(request(url));
    }

    public List<Group> albums(int limit) throws IOException {
        return parseGroups(request("api/library/groups?view=albums&paged=1&limit="
                + clampLimit(limit)), true);
    }

    public List<Group> artists(int limit) throws IOException {
        return parseGroups(request("api/library/groups?view=artists&paged=1&limit="
                + clampLimit(limit)), false);
    }

    /** Number of tracks the server currently knows about, for the rail badge. */
    // --------------------------------------------------------------- artwork

    /**
     * Absolute URL for a relative cover key produced by the library projection.
     *
     * <p>Both {@code cover/<id>?v=...} and {@code cover-asset/<id>?size=160}
     * are relative to the CGI root; the TV client asks for the 512px variant so
     * one request serves both the shelf thumbnail and the full-bleed hero.
     */
    public String coverUrl(String coverKey, int size) {
        if (coverKey == null || coverKey.isEmpty()) return "";
        String relative = coverKey;
        int cut = relative.indexOf('?');
        if (cut >= 0) relative = relative.substring(0, cut);
        if (relative.startsWith("cover/")) {
            relative = relative + "?size=" + size;
        } else if (relative.startsWith("cover-asset/")) {
            relative = relative + "?size=" + size;
        }
        return profile.fnAudioUrl() + relative;
    }

    /** Absolute playback URL for a track row. */
    public String mediaUrl(Track track) {
        return profile.fnAudioUrl() + "media/" + track.id + "?transcode=original";
    }

    /** Adds the same credentials the phone client uses in OkHttp mode. */
    public void authorize(Request.Builder builder) {
        if (profile.webSession) return;
        builder.header("Authorization", "Bearer " + profile.token);
        builder.header("X-Fnaudio-Trim-Token", profile.token);
        String cookie = cookieHeader();
        if (!cookie.isEmpty()) builder.header("Cookie", cookie);
    }

    String cookieHeader() {
        String encoded = SessionCookies.encodeToken(profile.token);
        return "fnaudio_trim_token=" + encoded
                + "; trim_token=" + encoded
                + "; token=" + encoded
                + "; fnos-token=" + encoded;
    }

    // ------------------------------------------------------------- internals

    private HttpUrl.Builder baseBuilder(String path) {
        HttpUrl parsed = HttpUrl.parse(profile.fnAudioUrl() + path);
        if (parsed == null) throw new IllegalArgumentException("bad fnAudio endpoint");
        return parsed.newBuilder();
    }

    private JSONObject request(String pathAndQuery) throws IOException {
        HttpUrl url = baseBuilder(pathAndQuery).build();
        return request(url);
    }

    private JSONObject request(HttpUrl url) throws IOException {
        Request.Builder builder = new Request.Builder().url(url).get();
        authorize(builder);
        Response response = null;
        try {
            response = client.newCall(builder.build()).execute();
            ResponseBody body = response.body();
            String text = body == null ? "" : body.string();
            if (!response.isSuccessful()) {
                throw new IOException("HTTP " + response.code() + " from " + url.encodedPath());
            }
            // The fnOS gateway answers an expired cookie with HTTP 200 and the
            // literal text "invalid token"; surface that as an auth failure
            // instead of an empty library so the TV can send the user back.
            if (SessionCookies.responseStatus(response.code(), text) == 401) {
                throw new TvAuthException();
            }
            try {
                return new JSONObject(text);
            } catch (Exception parse) {
                throw new IOException("unexpected payload from " + url.encodedPath(), parse);
            }
        } finally {
            if (response != null) response.close();
        }
    }

    private List<Track> parseTracks(JSONObject payload) {
        JSONArray rows = payload.optJSONArray("items");
        if (rows == null) return Collections.emptyList();
        List<Track> tracks = new ArrayList<>(rows.length());
        for (int index = 0; index < rows.length(); index++) {
            JSONObject row = rows.optJSONObject(index);
            if (row == null) continue;
            String id = text(row, "id", "");
            if (id.isEmpty()) continue;
            String coverKey = text(row, "cover_url", "");
            if (coverKey.isEmpty()) coverKey = text(row, "cover_thumbnail_url", "");
            tracks.add(new Track(
                    id,
                    text(row, "title", "未知曲目"),
                    text(row, "artist", "未知艺术家"),
                    text(row, "album", ""),
                    secondsToMillis(row),
                    text(row, "format", ""),
                    number(row, "track_no", 0),
                    coverKey));
        }
        return tracks;
    }

    private List<Group> parseGroups(JSONObject payload, boolean albumShape) {
        JSONArray rows = payload.optJSONArray("groups");
        if (rows == null) return Collections.emptyList();
        List<Group> groups = new ArrayList<>(rows.length());
        for (int index = 0; index < rows.length(); index++) {
            JSONObject row = rows.optJSONObject(index);
            if (row == null) continue;
            String name = text(row, "name", "");
            if (name.isEmpty()) continue;
            int count = number(row, "track_count", 0);
            String subtitle;
            if (albumShape) {
                String artist = text(row, "artist", "");
                subtitle = artist.isEmpty() ? count + " 首" : artist + " · " + count + " 首";
            } else {
                subtitle = count + " 首";
            }
            String coverId = text(row, "cover_track_id", "");
            groups.add(new Group(name, subtitle, count, coverId.isEmpty() ? "" : "cover/" + coverId));
        }
        return groups;
    }

    /**
     * Reads a string field with an explicit fallback.
     *
     * <p>The optional-read helpers are deliberately not used anywhere in the
     * Android sources: a missing key must produce a stated default at the call
     * site rather than an implicit empty value, which is what the repository
     * guard ``test_android_json_scan_has_no_implicit_opt_string_reads`` pins.
     */
    private static String text(JSONObject row, String key, String fallback) {
        String value;
        try {
            value = row.getString(key);
        } catch (JSONException missing) {
            return fallback;
        }
        if (value == null) return fallback;
        value = value.trim();
        return value.isEmpty() ? fallback : value;
    }

    private static int number(JSONObject row, String key, int fallback) {
        try {
            return row.getInt(key);
        } catch (JSONException missingOrNotANumber) {
            return fallback;
        }
    }

    private static double decimal(JSONObject row, String key, double fallback) {
        try {
            return row.getDouble(key);
        } catch (JSONException missingOrNotANumber) {
            return fallback;
        }
    }

    /**
     * Duration arrives as seconds (sometimes fractional) in older rows and as
     * milliseconds in newer ones. Anything above an hour in seconds is really a
     * millisecond value; the library never holds a 1000-hour track.
     */
    private static long secondsToMillis(JSONObject row) {
        double raw = decimal(row, "duration", 0);
        if (raw <= 0) return 0;
        if (raw > 36000) return Math.round(raw);
        return Math.round(raw * 1000);
    }

    private static int clampLimit(int limit) {
        return Math.max(1, Math.min(PAGE_LIMIT_MAX, limit));
    }

    /** Thrown when the stored token no longer authenticates. */
    public static final class TvAuthException extends IOException {
        TvAuthException() {
            super("fnAudio session is no longer valid");
        }
    }

    @Nullable
    static String formatDuration(long millis) {
        if (millis <= 0) return null;
        long totalSeconds = Math.round(millis / 1000.0);
        long hours = totalSeconds / 3600;
        long minutes = (totalSeconds % 3600) / 60;
        long seconds = totalSeconds % 60;
        if (hours > 0) {
            return String.format(Locale.ROOT, "%d:%02d:%02d", hours, minutes, seconds);
        }
        return String.format(Locale.ROOT, "%d:%02d", minutes, seconds);
    }
}
