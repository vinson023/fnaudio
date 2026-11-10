package com.fnaudio.client.tv;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * Builds the recommendation shelf list from the interfaces the server already
 * exposes.
 *
 * <p>Both reference clients receive their home page as a server-side DSL. We
 * have no recommendation backend, so the shelves are assembled here from three
 * existing calls: recent tracks, the account's favourites, and the album
 * grouping. Keeping the rule in one class means the page stays a dumb renderer
 * and the whole behaviour can be unit-tested without an Activity.
 *
 * <p>A shelf that fails is skipped rather than failing the page: a broken
 * favourites call must not blank the entire home screen.
 */
final class TvShelfData {
    /** One shelf: a heading and its cards. */
    static final class Shelf {
        final String title;
        final List<TvCardItem> cards;

        Shelf(String title, List<TvCardItem> cards) {
            this.title = title;
            this.cards = cards;
        }
    }

    private TvShelfData() {
    }

    static List<Shelf> build(TvApi api) throws IOException {
        List<Shelf> shelves = new ArrayList<>();

        List<TvApi.Track> recent = safe(api::recentTracks, 12);
        if (!recent.isEmpty()) {
            shelves.add(new Shelf("最近添加", trackCards(recent, recent)));
        }

        List<TvApi.Track> favorites = favorites(api);
        if (!favorites.isEmpty()) {
            shelves.add(new Shelf("我的收藏", trackCards(favorites, favorites)));
        }

        List<TvApi.Group> albums = safe(api::albums, 12);
        if (!albums.isEmpty()) {
            shelves.add(new Shelf("专辑", groupCards(albums, "album")));
        }

        List<TvApi.Group> artists = safe(api::artists, 12);
        if (!artists.isEmpty()) {
            shelves.add(new Shelf("艺术家", groupCards(artists, "artist")));
        }

        return shelves;
    }

    private static List<TvCardItem> trackCards(List<TvApi.Track> tracks,
                                               List<TvApi.Track> queue) {
        List<TvCardItem> cards = new ArrayList<>(tracks.size());
        for (TvApi.Track track : tracks) {
            cards.add(TvCardItem.ofTrack(track, queue));
        }
        return cards;
    }

    private static List<TvCardItem> groupCards(List<TvApi.Group> groups, String kind) {
        List<TvCardItem> cards = new ArrayList<>(groups.size());
        for (TvApi.Group group : groups) {
            cards.add(TvCardItem.ofGroup(kind + ":" + group.name, group.name,
                    group.subtitle, group.coverKey));
        }
        return cards;
    }

    /**
     * Favourites resolve through the account state, which needs a second call
     * to hydrate ids into tracks. An empty or failing state is not an error.
     */
    private static List<TvApi.Track> favorites(TvApi api) {
        try {
            TvApi.UserState state = api.userState();
            if (state.favoriteIds.isEmpty()) return new ArrayList<>();
            List<String> ids = state.favoriteIds.size() > 12
                    ? state.favoriteIds.subList(0, 12)
                    : state.favoriteIds;
            return api.tracksByIds(new ArrayList<>(ids));
        } catch (IOException | RuntimeException failure) {
            return new ArrayList<>();
        }
    }

    /** Runs one list query, turning any failure into an empty list. */
    private static <T> List<T> safe(Query<T> query, int limit) {
        try {
            List<T> value = query.run(limit);
            return value == null ? new ArrayList<>() : value;
        } catch (IOException | RuntimeException failure) {
            return new ArrayList<>();
        }
    }

    private interface Query<T> {
        List<T> run(int limit) throws IOException;
    }
}
