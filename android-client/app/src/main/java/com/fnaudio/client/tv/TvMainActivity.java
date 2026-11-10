package com.fnaudio.client.tv;

import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

/**
 * The television shell: a fixed left rail, a content area that swaps pages, and
 * a persistent now-playing strip along the bottom.
 *
 * <p>The rail only moves vertically and the content only moves horizontally,
 * which keeps the remote's four keys unambiguous. Opening an album or an artist
 * pushes a page and Back pops it, so the television never needs a breadcrumb.
 */
public final class TvMainActivity extends AppCompatActivity implements TvPlayer.Listener {
    public static final String EXTRA_PROFILE_ID = "com.fnaudio.client.tv.PROFILE_ID";

    private static final int PAGE_HOME = 0;
    private static final int PAGE_ALBUMS = 1;
    private static final int PAGE_ARTISTS = 2;
    private static final int PAGE_TRACKS = 3;
    private static final int PAGE_QUEUE = 4;

    private final ExecutorService io = Executors.newFixedThreadPool(3);
    private final List<View> railItems = new ArrayList<>();
    /** Rail entries in visual order, including the now-playing action. */
    private final List<View> railFocusables = new ArrayList<>();
    /** Rail entry per {@code PAGE_*} constant, so inserting an action cannot
     * shift which entry the highlight returns to. */
    private final Map<Integer, View> railPageItems = new HashMap<>();

    private SecureProfileStore store;
    private ConnectionProfile profile;
    private TvApi api;
    private TvArtworkLoader artwork;
    private TvPlayer player;
    private TvShelfNavigator navigator;

    private FrameLayout contentHost;
    private TvNowPlayingOverlay nowPlaying;
    private LinearLayout rail;

    private TextView stripTitle;
    private TextView stripSubtitle;
    private ProgressBar stripProgress;

    private int currentPage = PAGE_HOME;
    @Nullable private Runnable backAction;
    /** Where right on the rail sends the focus for the page currently shown. */
    @Nullable private Runnable contentFocusAction;
    private String pageTitle = "首页";

    private final List<TvApi.Track> recentCache = new ArrayList<>();
    private boolean homeLoaded;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        store = new SecureProfileStore(this);
        profile = resolveProfile();
        if (profile == null) {
            startActivity(new Intent(this, TvLoginActivity.class));
            finish();
            return;
        }
        api = new TvApi(this, profile);
        artwork = new TvArtworkLoader(api, com.fnaudio.client.network.HttpClientFactory
                .create(this, profile));
        player = new TvPlayer(this, api);
        player.setListener(this);
        navigator = new TvShelfNavigator();

        setContentView(buildShell());
        TvUi.hideSystemBars(this);
        selectPage(PAGE_HOME);
    }

    @Nullable
    private ConnectionProfile resolveProfile() {
        String id = getIntent().getStringExtra(EXTRA_PROFILE_ID);
        if (id != null && !id.isEmpty()) {
            ConnectionProfile found = store.find(id);
            if (found != null) return found;
        }
        return store.active();
    }

    // ------------------------------------------------------------------ shell

    private View buildShell() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(TvUi.BG);

        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.HORIZONTAL);
        root.addView(body, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        rail = new LinearLayout(this);
        rail.setOrientation(LinearLayout.VERTICAL);
        rail.setPadding(0, TvUi.dp(this, 36), 0, TvUi.dp(this, 96));

        // Ten entries no longer fit a 540dp-tall screen at 4K-friendly text
        // sizes. The rail scrolls; the remote's focus search brings the
        // highlighted entry back into view on its own.
        ScrollView railScroll = new ScrollView(this);
        railScroll.setBackgroundColor(0xFF0B0D11);
        railScroll.setVerticalScrollBarEnabled(false);
        railScroll.setFocusable(false);
        railScroll.addView(rail, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        body.addView(railScroll, new LinearLayout.LayoutParams(
                TvUi.dp(this, 136), ViewGroup.LayoutParams.MATCH_PARENT));

        addRailBrand();

        addRailItem("首页", PAGE_HOME);
        addRailItem("专辑", PAGE_ALBUMS);
        addRailItem("艺术家", PAGE_ARTISTS);
        addRailItem("曲目", PAGE_TRACKS);
        addRailItem("队列", PAGE_QUEUE);
        addRailAction("收藏", this::openFavorites);
        addRailAction("播放列表", this::openPlaylists);
        addRailAction("正在播放", this::openNowPlaying);
        addRailAction("搜索", this::openSearch);
        addRailAction("设置", this::openSettings);

        FrameLayout content = new FrameLayout(this);
        body.addView(content, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));

        contentHost = new FrameLayout(this);
        content.addView(contentHost, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        content.addView(buildNowPlayingStrip(), new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(this, 66), Gravity.BOTTOM));

        nowPlaying = new TvNowPlayingOverlay(this, player, api, artwork);
        nowPlaying.setOnClose(() -> {
            nowPlaying.hideLyrics();
            nowPlaying.setVisibility(View.GONE);
            focusRail();
        });
        root.addView(nowPlaying, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        nowPlaying.setVisibility(View.GONE);
        return root;
    }

    private void addRailBrand() {
        TextView brand = new TextView(this);
        brand.setText("fnAudio");
        brand.setTextColor(TvUi.TEXT);
        brand.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f);
        brand.setTypeface(null, android.graphics.Typeface.BOLD);
        brand.setPadding(TvUi.dp(this, 28), 0, 0, TvUi.dp(this, 16));
        rail.addView(brand);

        TextView hint = new TextView(this);
        hint.setText(profileName());
        hint.setTextColor(TvUi.TEXT_3);
        hint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f);
        hint.setPadding(TvUi.dp(this, 28), 0, TvUi.dp(this, 12), TvUi.dp(this, 14));
        hint.setSingleLine(true);
        hint.setEllipsize(TextUtils.TruncateAt.END);
        rail.addView(hint);
    }

    private void addRailItem(String label, int page) {
        TextView item = new TextView(this);
        item.setText(label);
        item.setTextColor(TvUi.TEXT_2);
        item.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f);
        item.setGravity(Gravity.CENTER_VERTICAL);
        item.setPadding(TvUi.dp(this, 28), 0, TvUi.dp(this, 12), 0);
        item.setFocusable(true);
        item.setFocusableInTouchMode(false);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(this, 50));
        params.bottomMargin = TvUi.dp(this, 2);
        item.setLayoutParams(params);
        item.setBackground(railBackground(false));
        item.setForeground(TvUi.focusRing(this, 10f));
        item.setTag(page);
        item.setOnFocusChangeListener((view, hasFocus) -> {
            // Focus alone must not change the page: browsing the rail with the
            // up and down keys would otherwise silently switch pages out from
            // under the viewer before they ever pressed OK.
            refreshRailColors();
        });
        item.setOnClickListener(view -> selectPage(page));
        attachRailKeys(item, true);
        rail.addView(item);
        railItems.add(item);
        railFocusables.add(item);
        railPageItems.put(page, item);
    }

    /** Rail entry that runs an action instead of switching pages. */
    private void addRailAction(String label, Runnable action) {
        TextView item = new TextView(this);
        item.setText(label);
        item.setTextColor(TvUi.TEXT_2);
        item.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        item.setGravity(Gravity.CENTER_VERTICAL);
        item.setPadding(TvUi.dp(this, 28), 0, TvUi.dp(this, 12), 0);
        item.setFocusable(true);
        item.setFocusableInTouchMode(false);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(this, 46));
        params.topMargin = TvUi.dp(this, 6);
        item.setLayoutParams(params);
        item.setBackground(railBackground(false));
        item.setForeground(TvUi.focusRing(this, 10f));
        item.setOnFocusChangeListener((view, hasFocus) -> {
            TextView target = (TextView) view;
            target.setBackground(railBackground(hasFocus));
            target.setTextColor(hasFocus ? TvUi.TEXT : TvUi.TEXT_3);
        });
        item.setOnClickListener(view -> action.run());
        attachRailKeys(item, false);
        rail.addView(item);
        railFocusables.add(item);
    }

    /**
     * Up and down belong to the rail while the rail has focus: the default focus
     * search treats the whole screen as one grid and happily jumps sideways into
     * the content, which on a remote feels like the highlight escaped. Right is
     * wired explicitly for the same reason.
     */
    private void attachRailKeys(View item, boolean isPageEntry) {
        item.setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
            if (keyCode == KeyEvent.KEYCODE_DPAD_UP || keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
                int index = railFocusables.indexOf(view);
                if (index < 0) return false;
                int next = keyCode == KeyEvent.KEYCODE_DPAD_UP ? index - 1 : index + 1;
                if (next < 0 || next >= railFocusables.size()) return false;
                railFocusables.get(next).requestFocus();
                return true;
            }
            if (isPageEntry && keyCode == KeyEvent.KEYCODE_DPAD_RIGHT
                    && contentFocusAction != null) {
                contentFocusAction.run();
                return true;
            }
            return false;
        });
    }

    private android.graphics.drawable.Drawable railBackground(boolean focused) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.RECTANGLE);
        drawable.setCornerRadius(TvUi.dp(this, 10));
        drawable.setColor(focused ? TvUi.PANEL_RAISED : Color.TRANSPARENT);
        return drawable;
    }

    /**
     * Keeps the rail readable while focus is out in the content: the entry for
     * the page on screen stays bright, everything else recedes.
     */
    private void refreshRailColors() {
        for (View item : railItems) {
            if (!(item instanceof TextView)) continue;
            TextView label = (TextView) item;
            Object tag = item.getTag();
            boolean active = tag instanceof Integer && (Integer) tag == currentPage;
            boolean focused = item.isFocused();
            label.setTextColor(focused || active ? TvUi.TEXT : TvUi.TEXT_2);
            item.setBackground(railBackground(focused));
        }
    }

    private View buildNowPlayingStrip() {
        LinearLayout strip = new LinearLayout(this);
        strip.setOrientation(LinearLayout.VERTICAL);
        // Opaque: content scrolls underneath this bar, and at 94% alpha the
        // shelf tiles showed through as ghostly rectangles that read as a
        // rendering fault. A hairline on top is the only seam it needs.
        strip.setBackgroundColor(0xFF0E1013);

        View divider = new View(this);
        divider.setBackgroundColor(0xFF232830);
        strip.addView(divider, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, TvUi.dp(this, 1f))));

        populateNowPlayingStrip(strip);
        return strip;
    }

    private void populateNowPlayingStrip(LinearLayout strip) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(TvUi.dp(this, 32), 0, TvUi.dp(this, 32), 0);
        row.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(this, 60)));
        strip.addView(row);

        stripTitle = new TextView(this);
        stripTitle.setText("还没有在播放");
        stripTitle.setTextColor(TvUi.TEXT_2);
        stripTitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        stripTitle.setSingleLine(true);
        stripTitle.setEllipsize(TextUtils.TruncateAt.END);
        row.addView(stripTitle, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        stripSubtitle = new TextView(this);
        stripSubtitle.setTextColor(TvUi.TEXT_3);
        stripSubtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f);
        row.addView(stripSubtitle);

        stripProgress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        stripProgress.setMax(1000);
        stripProgress.setProgressTintList(android.content.res.ColorStateList.valueOf(TvUi.ACCENT));
        stripProgress.setProgressBackgroundTintList(
                android.content.res.ColorStateList.valueOf(0xFF272B31));
        stripProgress.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, TvUi.dp(this, 2f))));
        strip.addView(stripProgress);
    }

    // ------------------------------------------------------------------ pages

    private void selectPage(int page) {
        currentPage = page;
        backAction = null;
        contentFocusAction = null;
        navigator.clear();
        switch (page) {
            case PAGE_ALBUMS:
                pageTitle = "专辑";
                showAlbumsPage();
                break;
            case PAGE_ARTISTS:
                pageTitle = "艺术家";
                showArtistsPage();
                break;
            case PAGE_TRACKS:
                pageTitle = "全部曲目";
                showAllTracksPage();
                break;
            case PAGE_QUEUE:
                pageTitle = "队列";
                showQueuePage();
                break;
            case PAGE_HOME:
            default:
                pageTitle = "首页";
                showHomePage();
                break;
        }
        refreshRailColors();
    }

    private void showHomePage() {
        ScrollView scroll = new ScrollView(this);
        scroll.setClipToPadding(false);
        scroll.setPadding(0, 0, 0, TvUi.dp(this, 80));
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(column);

        navigator.attach(scroll, TvUi.dp(this, 24));
        // Up out of the first row returns to the quick entries, then to the
        // hero; anything else is a dead end the remote would otherwise punish
        // by dropping the highlight.
        navigator.setEdgeListener((from, position, direction) -> {
            if (direction < 0) {
                if (quickChips != null && quickChips.getChildCount() > 0) {
                    quickChips.getChildAt(0).requestFocus();
                    return true;
                }
                if (heroAction != null) {
                    heroAction.requestFocus();
                    return true;
                }
            }
            return false;
        });
        contentFocusAction = () -> navigator.focusRow(0, navigator.lastColumn());

        FrameLayout hero = buildHero();
        column.addView(hero, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(this, 196)));

        column.addView(buildQuickChips());

        TvShelfView recent = new TvShelfView(this, navigator, artwork, "最近添加", 118);
        recent.setOnItemClick((item, position) -> {
            if (item.payload instanceof TvApi.Track) {
                player.play(recentCache, position);
            }
        });
        applyLeftEdge(recent);
        column.addView(recent);

        TvShelfView albums = new TvShelfView(this, navigator, artwork, "专辑", 118);
        albums.setOnItemClick((item, position) -> {
            if (item.payload instanceof TvApi.Group) openAlbum((TvApi.Group) item.payload);
        });
        applyLeftEdge(albums);
        column.addView(albums);

        TvShelfView artists = new TvShelfView(this, navigator, artwork, "艺术家", 118);
        artists.setOnItemClick((item, position) -> {
            if (item.payload instanceof TvApi.Group) openArtist((TvApi.Group) item.payload);
        });
        applyLeftEdge(artists);
        column.addView(artists);

        contentHost.removeAllViews();
        contentHost.addView(scroll, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        loadHome(recent, albums, artists);
    }

    private TextView heroTitle;
    private TextView heroMeta;
    private TextView heroAction;
    private ImageView heroBackdrop;
    @Nullable private LinearLayout quickChips;

    /**
     * The library views that are not worth a permanent rail entry.
     *
     * <p>Genres, composers, DSD and the random hundred are browsed far less
     * often than albums or artists, so they live one press below the hero
     * instead of lengthening the rail to the point where the last entry only
     * exists after scrolling.
     */
    private LinearLayout buildQuickChips() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setPadding(TvUi.dp(this, 32), TvUi.dp(this, 14),
                TvUi.dp(this, 32), TvUi.dp(this, 4));
        quickChips = row;

        addQuickChip(row, "类型", () -> showCreatorGroups("类型", "genres"));
        addQuickChip(row, "作曲者", () -> showCreatorGroups("作曲者", "composers"));
        addQuickChip(row, "DSD", () -> openFlatView("DSD 音乐", "dsd"));
        addQuickChip(row, "随机 100", () -> openFlatView("随机 100 首", "random100"));
        return row;
    }

    private void addQuickChip(LinearLayout row, String label, Runnable action) {
        TextView chip = new TextView(this);
        chip.setText(label);
        chip.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        chip.setGravity(Gravity.CENTER);
        chip.setFocusable(true);
        chip.setFocusableInTouchMode(false);
        chip.setPadding(TvUi.dp(this, 22), 0, TvUi.dp(this, 22), 0);

        GradientDrawable idle = chipBackground(false);
        GradientDrawable focused = chipBackground(true);
        android.graphics.drawable.StateListDrawable states =
                new android.graphics.drawable.StateListDrawable();
        states.addState(new int[]{android.R.attr.state_focused}, focused);
        states.addState(new int[]{}, idle);
        chip.setBackground(states);
        chip.setForeground(TvUi.focusRing(this, 20f));
        chip.setTextColor(TvUi.TEXT_2);
        chip.setOnFocusChangeListener((view, hasFocus) ->
                ((TextView) view).setTextColor(hasFocus ? TvUi.TEXT : TvUi.TEXT_2));

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, TvUi.dp(this, 40));
        params.rightMargin = TvUi.dp(this, 10);
        chip.setLayoutParams(params);

        chip.setOnClickListener(view -> action.run());
        chip.setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
            if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
                return navigator.focusRow(0, 0);
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_UP) {
                if (heroAction != null && heroAction.getVisibility() == View.VISIBLE) {
                    heroAction.requestFocus();
                    return true;
                }
                return false;
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT && row.indexOfChild(view) == 0) {
                focusRail();
                return true;
            }
            return false;
        });
        row.addView(chip);
    }

    private GradientDrawable chipBackground(boolean focused) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setShape(GradientDrawable.RECTANGLE);
        drawable.setCornerRadius(TvUi.dp(this, 20));
        drawable.setColor(focused ? TvUi.PANEL_RAISED : 0xFF14171B);
        drawable.setStroke(Math.max(1, TvUi.dp(this, 1)),
                focused ? TvUi.ACCENT : 0xFF272B31);
        return drawable;
    }

    private FrameLayout buildHero() {
        FrameLayout hero = new FrameLayout(this);
        hero.setClipChildren(false);

        ImageView backdrop = new ImageView(this);
        backdrop.setScaleType(ImageView.ScaleType.CENTER_CROP);
        backdrop.setAlpha(0.55f);
        heroBackdrop = backdrop;
        hero.addView(backdrop, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        GradientDrawable fade = new GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{0xF207080A, 0xC407080A, 0x0007080A});
        View veil = new View(this);
        veil.setBackground(fade);
        hero.addView(veil, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout copy = new LinearLayout(this);
        copy.setOrientation(LinearLayout.VERTICAL);
        copy.setGravity(Gravity.CENTER_VERTICAL);
        copy.setPadding(TvUi.dp(this, 48), 0, TvUi.dp(this, 48), 0);
        hero.addView(copy, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        TextView kicker = new TextView(this);
        kicker.setText("继续聆听");
        kicker.setTextColor(TvUi.ACCENT);
        kicker.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        kicker.setLetterSpacing(0.12f);
        copy.addView(kicker);

        TextView title = new TextView(this);
        title.setText("正在载入音乐库…");
        title.setTextColor(TvUi.TEXT);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 30f);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        title.setMaxLines(2);
        title.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
                TvUi.dp(this, 420), ViewGroup.LayoutParams.WRAP_CONTENT);
        titleParams.topMargin = TvUi.dp(this, 12);
        copy.addView(title, titleParams);
        heroTitle = title;

        TextView meta = new TextView(this);
        meta.setTextColor(TvUi.TEXT_2);
        meta.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f);
        meta.setPadding(0, TvUi.dp(this, 10), 0, TvUi.dp(this, 26));
        copy.addView(meta);
        heroMeta = meta;

        TextView action = pillButton("开始播放");
        copy.addView(action, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        heroAction = action;

        return hero;
    }

    private TextView pillButton(String label) {
        TextView button = new TextView(this);
        button.setText(label);
        button.setTextColor(Color.BLACK);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
        button.setTypeface(null, android.graphics.Typeface.BOLD);
        button.setGravity(Gravity.CENTER);
        button.setFocusable(true);
        button.setFocusableInTouchMode(false);
        button.setPadding(TvUi.dp(this, 30), TvUi.dp(this, 12),
                TvUi.dp(this, 30), TvUi.dp(this, 12));
        // A white pill cannot signal focus with a white ring — the two merge.
        // The focus state therefore adds a blue outline, which stays legible
        // against both the button and the dark hero behind it.
        GradientDrawable idle = new GradientDrawable();
        idle.setShape(GradientDrawable.RECTANGLE);
        idle.setCornerRadius(TvUi.dp(this, 24));
        idle.setColor(Color.WHITE);

        GradientDrawable focused = new GradientDrawable();
        focused.setShape(GradientDrawable.RECTANGLE);
        focused.setCornerRadius(TvUi.dp(this, 24));
        focused.setColor(Color.WHITE);
        focused.setStroke(Math.max(3, TvUi.dp(this, 3)), TvUi.ACCENT);

        android.graphics.drawable.StateListDrawable states =
                new android.graphics.drawable.StateListDrawable();
        states.addState(new int[]{android.R.attr.state_focused}, focused);
        states.addState(new int[]{}, idle);
        button.setBackground(states);
        TvUi.applyFocusScale(button, 1.06f);
        return button;
    }

    private void loadHome(TvShelfView recent, TvShelfView albums, TvShelfView artists) {
        io.execute(() -> {
            try {
                List<TvApi.Track> tracks = api.recentTracks(24);
                List<TvApi.Group> albumRows = api.albums(24);
                List<TvApi.Group> artistRows = api.artists(24);
                runOnUiThread(() -> {
                    recentCache.clear();
                    recentCache.addAll(tracks);

                    List<TvShelfView.Item> recentItems = new ArrayList<>();
                    for (TvApi.Track track : tracks) {
                        recentItems.add(new TvShelfView.Item(track.title,
                                track.artist, track.coverKey, track));
                    }
                    recent.setItems(recentItems);

                    List<TvShelfView.Item> albumItems = new ArrayList<>();
                    for (TvApi.Group group : albumRows) {
                        albumItems.add(new TvShelfView.Item(group.name,
                                group.subtitle, group.coverKey, group));
                    }
                    albums.setItems(albumItems);

                    List<TvShelfView.Item> artistItems = new ArrayList<>();
                    for (TvApi.Group group : artistRows) {
                        artistItems.add(new TvShelfView.Item(group.name,
                                group.subtitle, group.coverKey, group));
                    }
                    artists.setItems(artistItems);

                    bindHero(tracks);
                    homeLoaded = true;
                });
            } catch (Exception error) {
                runOnUiThread(() -> showError(error));
            }
        });
    }

    private void bindHero(List<TvApi.Track> tracks) {
        if (heroTitle == null) return;
        if (tracks.isEmpty()) {
            heroTitle.setText("音乐库里还没有歌曲");
            heroMeta.setText("先在 fnAudio 里完成一次扫描");
            heroAction.setVisibility(View.GONE);
            return;
        }
        TvApi.Track first = tracks.get(0);
        heroTitle.setText(first.title);
        heroMeta.setText(first.artist + (first.album.isEmpty() ? "" : " · " + first.album));
        artwork.loadHires(first.coverKey, heroBackdrop);
        heroAction.setOnClickListener(view -> player.play(recentCache, 0));
        heroAction.setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
            if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
                if (quickChips != null && quickChips.getChildCount() > 0) {
                    quickChips.getChildAt(0).requestFocus();
                    return true;
                }
                return navigator.focusRow(0, 0);
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_UP || keyCode == KeyEvent.KEYCODE_DPAD_LEFT) {
                focusRail();
                return true;
            }
            return false;
        });
    }

    /** Left on the first tile of a shelf returns to the rail. */
    private void applyLeftEdge(TvShelfView shelf) {
        shelf.setOnLeftEdge(position -> {
            focusRail();
            return true;
        });
    }

    /** Puts the highlight back on the rail entry of the page being shown. */
    private void focusRail() {
        View entry = railPageItems.get(currentPage);
        if (entry == null && !railFocusables.isEmpty()) entry = railFocusables.get(0);
        if (entry != null) entry.requestFocus();
    }

    private void showAlbumsPage() {
        View page = buildBrowseGrid("专辑", () -> api.albums(120),
                group -> openAlbum(group));
        contentHost.removeAllViews();
        contentHost.addView(page);
    }

    private void showArtistsPage() {
        View page = buildBrowseGrid("艺术家", () -> api.artists(120),
                group -> openArtist(group));
        contentHost.removeAllViews();
        contentHost.addView(page);
    }

    private interface GroupLoader {
        List<TvApi.Group> load() throws Exception;
    }

    private View buildBrowseGrid(String title, GroupLoader loader,
                                 Consumer<TvApi.Group> onClick) {
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);

        container.addView(pageHeading(title));

        FrameLayout stack = new FrameLayout(this);
        container.addView(stack, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        TvCardGridView grid = new TvCardGridView(this, artwork, 6, 116);
        grid.setOnItemClick((item, position) -> {
            if (item.payload instanceof TvApi.Group) onClick.accept((TvApi.Group) item.payload);
        });
        grid.setOnLeftEdge(position -> {
            focusRail();
            return true;
        });
        contentFocusAction = grid::focusFirst;
        stack.addView(grid, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        View loading = loadingView("正在载入" + title + "…");
        stack.addView(loading, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        io.execute(() -> {
            try {
                List<TvApi.Group> groups = loader.load();
                runOnUiThread(() -> {
                    loading.setVisibility(View.GONE);
                    List<TvShelfView.Item> items = new ArrayList<>();
                    for (TvApi.Group group : groups) {
                        items.add(new TvShelfView.Item(group.name, group.subtitle,
                                group.coverKey, group));
                    }
                    grid.setItems(items);
                    grid.focusFirst();
                });
            } catch (Exception error) {
                runOnUiThread(() -> loading.setVisibility(View.GONE));
                runOnUiThread(() -> showError(error));
            }
        });
        return container;
    }

    private final List<TvApi.Track> allTracksData = new ArrayList<>();
    @Nullable private TvTrackListView allTracksList;
    @Nullable private TvTrackListView queueList;

    private void showAllTracksPage() {
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.addView(pageHeading("全部曲目"));

        TvTrackListView list = new TvTrackListView(this, artwork);
        allTracksList = list;
        list.setOnTrackClick((track, position) -> player.play(allTracksData, position));
        list.setOnLeftEdge(position -> {
            focusRail();
            return true;
        });
        contentFocusAction = list::focusFirst;
        container.addView(list, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        contentHost.removeAllViews();
        contentHost.addView(container);

        io.execute(() -> {
            try {
                List<TvApi.Track> tracks = api.allTracks(300);
                runOnUiThread(() -> {
                    allTracksData.clear();
                    allTracksData.addAll(tracks);
                    list.setTracks(tracks);
                    list.setNowPlayingId(currentTrackId());
                    list.focusFirst();
                });
            } catch (Exception error) {
                runOnUiThread(() -> showError(error));
            }
        });
    }

    private void openAlbum(TvApi.Group album) {
        openTrackCollection(album.name, album.subtitle,
                () -> api.albumTracks(album.name, 200), album.coverKey);
    }

    private void openArtist(TvApi.Group artist) {
        openTrackCollection(artist.name, artist.subtitle,
                () -> api.artistTracks(artist.name, 200), artist.coverKey);
    }

    private void openTrackCollection(String title, String subtitle,
                                     Callable<List<TvApi.Track>> loader,
                                     String coverKey) {
        openTrackCollection(title, subtitle, loader, coverKey, null);
    }

    /**
     * Pushes a track list.
     *
     * <p>{@code back} exists because not every push comes from a rail page: a
     * playlist list and a genre grid both sit one level above the tracks they
     * open, and Back has to return there rather than skipping to the home page.
     */
    private void openTrackCollection(String title, String subtitle,
                                     Callable<List<TvApi.Track>> loader,
                                     String coverKey, @Nullable Runnable back) {
        final int originPage = currentPage;
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(TvUi.dp(this, 32), TvUi.dp(this, 24),
                TvUi.dp(this, 32), TvUi.dp(this, 8));

        ImageView cover = new ImageView(this);
        cover.setScaleType(ImageView.ScaleType.CENTER_CROP);
        TvUi.roundClip(cover, 10f);
        LinearLayout.LayoutParams coverParams = new LinearLayout.LayoutParams(
                TvUi.dp(this, 88), TvUi.dp(this, 88));
        coverParams.rightMargin = TvUi.dp(this, 24);
        header.addView(cover, coverParams);
        artwork.load(coverKey, cover);

        LinearLayout labels = new LinearLayout(this);
        labels.setOrientation(LinearLayout.VERTICAL);
        header.addView(labels);

        TextView name = new TextView(this);
        name.setText(title);
        name.setTextColor(TvUi.TEXT);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f);
        name.setTypeface(null, android.graphics.Typeface.BOLD);
        labels.addView(name);

        TextView detail = new TextView(this);
        detail.setText(subtitle);
        detail.setTextColor(TvUi.TEXT_3);
        detail.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        labels.addView(detail);

        container.addView(header);

        TvTrackListView list = new TvTrackListView(this, artwork);
        container.addView(list, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        list.setOnLeftEdge(position -> {
            focusRail();
            return true;
        });
        contentFocusAction = list::focusFirst;

        contentHost.removeAllViews();
        contentHost.addView(container);
        backAction = () -> {
            backAction = null;
            if (back != null) {
                back.run();
                return;
            }
            selectPage(originPage);
            focusRail();
        };
        final java.util.concurrent.atomic.AtomicReference<List<TvApi.Track>> holder =
                new java.util.concurrent.atomic.AtomicReference<>(new ArrayList<>());
        list.setOnTrackClick((track, position) -> player.play(holder.get(), position));
        contentFocusAction = list::focusFirst;

        io.execute(() -> {
            try {
                List<TvApi.Track> tracks = loader.call();
                holder.set(tracks);
                runOnUiThread(() -> {
                    list.setTracks(tracks);
                    list.setNowPlayingId(currentTrackId());
                    // The group subtitle already carries its track count for
                    // both albums and artists, so appending another one printed
                    // "余温乐队 · 4 首 · 4 首".
                    detail.setText(subtitle.contains("首") ? subtitle
                            : subtitle.isEmpty() ? tracks.size() + " 首"
                            : subtitle + " · " + tracks.size() + " 首");
                    list.focusFirst();
                });
            } catch (Exception error) {
                runOnUiThread(() -> showError(error));
            }
        });
    }

    // ------------------------------------------------------- account & views

    /** Favourites: ids live in the account state, rows come from the library. */
    private void openFavorites() {
        openTrackCollection("收藏歌曲", "来自你的账号", () -> {
            TvApi.UserState state = api.userState();
            return api.tracksByIds(state.favoriteIds);
        }, "");
    }

    /** Playlist names, then the tracks of the one that is opened. */
    private void openPlaylists() {
        final int origin = currentPage;
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.addView(pageHeading("播放列表"));

        FrameLayout stack = new FrameLayout(this);
        container.addView(stack, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        ScrollView scroll = new ScrollView(this);
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setPadding(TvUi.dp(this, 32), 0, TvUi.dp(this, 32), TvUi.dp(this, 72));
        scroll.addView(column);
        stack.addView(scroll);

        View loading = loadingView("正在载入播放列表…");
        stack.addView(loading, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        contentHost.removeAllViews();
        contentHost.addView(container);
        backAction = () -> {
            backAction = null;
            selectPage(origin);
            focusRail();
        };
        contentFocusAction = () -> {
            if (column.getChildCount() > 0) column.getChildAt(0).requestFocus();
        };

        io.execute(() -> {
            try {
                TvApi.UserState state = api.userState();
                runOnUiThread(() -> {
                    loading.setVisibility(View.GONE);
                    if (state.playlists.isEmpty()) {
                        column.addView(emptyHint("还没有播放列表，可以在手机上新建后再回到电视"));
                        return;
                    }
                    for (TvApi.Playlist playlist : state.playlists) {
                        LinearLayout row = menuRow(playlist.name,
                                playlist.trackIds.size() + " 首");
                        row.setOnClickListener(view -> openPlaylist(playlist));
                        column.addView(row);
                    }
                    contentFocusAction.run();
                });
            } catch (Exception error) {
                runOnUiThread(() -> loading.setVisibility(View.GONE));
                runOnUiThread(() -> showError(error));
            }
        });
    }

    private void openPlaylist(TvApi.Playlist playlist) {
        openTrackCollection(playlist.name, playlist.trackIds.size() + " 首 · 播放列表",
                () -> api.tracksByIds(playlist.trackIds), "", this::openPlaylists);
    }

    /** Genre or composer grid; a card opens that creator's tracks. */
    private void showCreatorGroups(String title, String view) {
        View page = buildBrowseGrid(title, () -> api.groupsByView(view, 200),
                group -> openTrackCollection(group.name, group.subtitle,
                        () -> api.creatorTracks(view, group.name, 200), group.coverKey,
                        () -> showCreatorGroups(title, view)));
        contentHost.removeAllViews();
        contentHost.addView(page);
        backAction = () -> {
            backAction = null;
            selectPage(PAGE_HOME);
            focusRail();
        };
    }

    /** A flat library view played as one list: DSD or the random hundred. */
    private void openFlatView(String title, String view) {
        openTrackCollection(title, "", () -> api.tracksByView(view, 300), "");
    }

    /** Text search over title, artist and album. */
    private void openSearch() {
        final int origin = currentPage;
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.addView(pageHeading("搜索"));

        EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setHint("输入歌名、歌手或专辑，按搜索键确认");
        field.setHintTextColor(TvUi.TEXT_3);
        field.setTextColor(TvUi.TEXT);
        field.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f);
        field.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH);
        GradientDrawable fieldBackground = new GradientDrawable();
        fieldBackground.setShape(GradientDrawable.RECTANGLE);
        fieldBackground.setCornerRadius(TvUi.dp(this, 10));
        fieldBackground.setColor(0xFF14171B);
        fieldBackground.setStroke(Math.max(1, TvUi.dp(this, 1)), 0xFF272B31);
        field.setBackground(fieldBackground);
        field.setPadding(TvUi.dp(this, 18), 0, TvUi.dp(this, 18), 0);
        LinearLayout.LayoutParams fieldParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(this, 46));
        fieldParams.leftMargin = TvUi.dp(this, 32);
        fieldParams.rightMargin = TvUi.dp(this, 32);
        fieldParams.bottomMargin = TvUi.dp(this, 10);
        container.addView(field, fieldParams);

        TextView status = new TextView(this);
        status.setText("输入关键词后按搜索键");
        status.setTextColor(TvUi.TEXT_3);
        status.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        status.setPadding(TvUi.dp(this, 34), 0, TvUi.dp(this, 32), TvUi.dp(this, 6));
        container.addView(status);

        TvTrackListView list = new TvTrackListView(this, artwork);
        container.addView(list, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        list.setOnLeftEdge(position -> {
            focusRail();
            return true;
        });

        final List<TvApi.Track> results = new ArrayList<>();
        list.setOnTrackClick((track, position) -> player.play(results, position));

        contentHost.removeAllViews();
        contentHost.addView(container);
        backAction = () -> {
            backAction = null;
            selectPage(origin);
            focusRail();
        };
        contentFocusAction = field::requestFocus;

        Runnable submit = () -> {
            String query = field.getText().toString().trim();
            if (query.isEmpty()) {
                status.setText("请输入关键词");
                return;
            }
            status.setText("正在搜索…");
            io.execute(() -> {
                try {
                    List<TvApi.Track> tracks = api.searchTracks(query, 200);
                    runOnUiThread(() -> {
                        results.clear();
                        results.addAll(tracks);
                        list.setTracks(tracks);
                        list.setNowPlayingId(currentTrackId());
                        status.setText(tracks.isEmpty()
                                ? "没有找到匹配的歌曲" : "找到 " + tracks.size() + " 首");
                        if (!tracks.isEmpty()) list.focusFirst();
                    });
                } catch (Exception error) {
                    runOnUiThread(() -> showError(error));
                }
            });
        };
        field.setOnEditorActionListener((view, actionId, event) -> {
            submit.run();
            return true;
        });
        // A remote without a usable soft keyboard can still re-run the last
        // query: OK on the list plays, and Back returns to the rail.
        field.setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
            if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
                list.focusFirst();
                return true;
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT) {
                focusRail();
                return true;
            }
            return false;
        });
        field.requestFocus();
    }

    /** Connection details, switching server, and signing out. */
    private void openSettings() {
        final int origin = currentPage;
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.addView(pageHeading("设置"));

        ScrollView scroll = new ScrollView(this);
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setPadding(TvUi.dp(this, 32), 0, TvUi.dp(this, 32), TvUi.dp(this, 72));
        scroll.addView(column);
        container.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        column.addView(infoRow("当前连接", profileName()));
        column.addView(infoRow("服务器", profile.host + ":" + profile.port));
        column.addView(infoRow("客户端版本", com.fnaudio.client.BuildConfig.VERSION_NAME));

        LinearLayout switchServer = menuRow("切换服务器", "回到连接页选择另一个已保存的设备");
        switchServer.setOnClickListener(view -> {
            store.setActive("");
            startActivity(new Intent(this, TvLoginActivity.class));
            finish();
        });
        column.addView(switchServer);

        LinearLayout logout = menuRow("退出登录", "清除这台电视上的登录状态");
        logout.setOnClickListener(view -> {
            store.setActive("");
            startActivity(new Intent(this, TvLoginActivity.class));
            finish();
        });
        column.addView(logout);

        contentHost.removeAllViews();
        contentHost.addView(container);
        backAction = () -> {
            backAction = null;
            selectPage(origin);
            focusRail();
        };
        contentFocusAction = () -> {
            if (column.getChildCount() > 2) column.getChildAt(2).requestFocus();
        };
    }

    private LinearLayout menuRow(String label, String detail) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(TvUi.dp(this, 18), 0, TvUi.dp(this, 18), 0);
        row.setFocusable(true);
        row.setFocusableInTouchMode(false);
        row.setClickable(true);
        row.setBackground(railBackground(false));
        row.setForeground(TvUi.focusRing(this, 10f));

        TextView name = new TextView(this);
        name.setText(label);
        name.setTextColor(TvUi.TEXT);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f);
        row.addView(name, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView meta = new TextView(this);
        meta.setText(detail);
        meta.setTextColor(TvUi.TEXT_3);
        meta.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        row.addView(meta);

        row.setOnFocusChangeListener((view, hasFocus) ->
                view.setBackground(railBackground(hasFocus)));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(this, 52));
        params.bottomMargin = TvUi.dp(this, 2);
        row.setLayoutParams(params);
        return row;
    }

    private View infoRow(String label, String value) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(TvUi.dp(this, 18), 0, TvUi.dp(this, 18), 0);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvUi.dp(this, 44));
        row.setLayoutParams(params);

        TextView name = new TextView(this);
        name.setText(label);
        name.setTextColor(TvUi.TEXT_3);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        row.addView(name, new LinearLayout.LayoutParams(
                TvUi.dp(this, 160), ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView detail = new TextView(this);
        detail.setText(value);
        detail.setTextColor(TvUi.TEXT);
        detail.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        row.addView(detail);
        return row;
    }

    private TextView emptyHint(String text) {
        TextView hint = new TextView(this);
        hint.setText(text);
        hint.setTextColor(TvUi.TEXT_3);
        hint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        hint.setPadding(TvUi.dp(this, 16), TvUi.dp(this, 20), 0, 0);
        return hint;
    }

    private void showQueuePage() {
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.addView(pageHeading("队列"));

        TvTrackListView list = new TvTrackListView(this, artwork);
        queueList = list;
        list.setOnTrackClick((track, position) -> player.playAt(position));
        list.setOnLeftEdge(position -> {
            focusRail();
            return true;
        });
        contentFocusAction = list::focusFirst;
        container.addView(list, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        contentHost.removeAllViews();
        contentHost.addView(container);

        List<TvApi.Track> queue = new ArrayList<>(player.queue());
        list.setTracks(queue);
        list.setNowPlayingId(currentTrackId());
        if (!queue.isEmpty()) list.focusFirst();
    }

    /** Repaints the queue in place; rebuilding the page would drop the focus. */
    private void refreshQueueList() {
        if (queueList == null) return;
        queueList.setTracks(new ArrayList<>(player.queue()));
        queueList.setNowPlayingId(currentTrackId());
    }

    // ------------------------------------------------------------------ chrome

    private View pageHeading(String text) {
        TextView heading = new TextView(this);
        heading.setText(text);
        heading.setTextColor(TvUi.TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f);
        heading.setTypeface(null, android.graphics.Typeface.BOLD);
        heading.setPadding(TvUi.dp(this, 32), TvUi.dp(this, 26),
                TvUi.dp(this, 32), TvUi.dp(this, 12));
        return heading;
    }

    private View loadingView(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextColor(TvUi.TEXT_3);
        view.setTextSize(TvUi.sp(this, 16f));
        view.setGravity(Gravity.CENTER);
        return view;
    }

    private void showError(Exception error) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setBackgroundColor(TvUi.BG);

        TextView message = new TextView(this);
        message.setText(error instanceof TvApi.TvAuthException
                ? "登录已过期，请重新连接"
                : "加载失败：" + friendly(error));
        message.setTextColor(TvUi.TEXT_2);
        message.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f);
        message.setGravity(Gravity.CENTER);
        box.addView(message);

        TextView retry = pillButton("重新加载");
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.topMargin = TvUi.dp(this, 22);
        box.addView(retry, params);
        retry.setOnClickListener(view -> selectPage(currentPage));

        TextView back = new TextView(this);
        back.setText("返回连接页");
        back.setTextColor(TvUi.TEXT_3);
        back.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        back.setGravity(Gravity.CENTER);
        back.setFocusable(true);
        back.setPadding(0, TvUi.dp(this, 18), 0, 0);
        back.setOnClickListener(view -> {
            store.setActive("");
            startActivity(new Intent(this, TvLoginActivity.class));
            finish();
        });
        box.addView(back);

        contentHost.removeAllViews();
        contentHost.addView(box);
        retry.requestFocus();
    }

    private static String friendly(Exception error) {
        String message = error.getMessage();
        return message == null || message.isEmpty() ? error.getClass().getSimpleName() : message;
    }

    private String profileName() {
        return profile == null || profile.name == null || profile.name.isEmpty()
                ? "未命名连接" : profile.name;
    }

    @Nullable
    private String currentTrackId() {
        TvApi.Track track = player.current();
        return track == null ? null : track.id;
    }

    // ------------------------------------------------------------------ player

    @Override
    public void onTrackChanged(@Nullable TvApi.Track track, int index) {
        if (track == null) {
            stripTitle.setText("还没有在播放");
            stripSubtitle.setText("");
            return;
        }
        stripTitle.setText(track.title);
        stripSubtitle.setText(track.artist);
        stripProgress.setProgress(0);
        nowPlaying.onTrackChanged(track);
        if (currentPage == PAGE_QUEUE) refreshQueueList();
        if (allTracksList != null && currentPage == PAGE_TRACKS) {
            allTracksList.setNowPlayingId(track.id);
        }
    }

    @Override
    public void onPlayingChanged(boolean playing) {
        stripSubtitle.setText(playing ? "正在播放" : "已暂停");
        nowPlaying.onPlayingChanged(playing);
    }

    @Override
    public void onProgress(long positionMs, long durationMs) {
        int value = durationMs <= 0 ? 0 : (int) Math.min(1000,
                Math.round(positionMs * 1000.0 / durationMs));
        stripProgress.setProgress(value);
        nowPlaying.onProgress(positionMs, durationMs);
    }

    @Override
    public void onQueueChanged() {
        if (currentPage == PAGE_QUEUE) refreshQueueList();
    }

    // ------------------------------------------------------------------- keys

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (nowPlaying != null && nowPlaying.getVisibility() == View.VISIBLE) {
            return nowPlaying.handleKey(keyCode, event) || super.onKeyDown(keyCode, event);
        }
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (backAction != null) {
                backAction.run();
                return true;
            }
            if (currentPage != PAGE_HOME) {
                selectPage(PAGE_HOME);
                View home = railPageItems.get(PAGE_HOME);
                if (home != null) home.requestFocus();
                return true;
            }
            if (nowPlaying != null && player.current() != null) {
                openNowPlaying();
                return true;
            }
        }
        if (keyCode == KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
                || keyCode == KeyEvent.KEYCODE_MEDIA_PLAY
                || keyCode == KeyEvent.KEYCODE_MEDIA_PAUSE) {
            player.toggle();
            return true;
        }
        if (keyCode == KeyEvent.KEYCODE_MEDIA_NEXT) {
            player.next();
            return true;
        }
        if (keyCode == KeyEvent.KEYCODE_MEDIA_PREVIOUS) {
            player.previous();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    private void openNowPlaying() {
        nowPlaying.setVisibility(View.VISIBLE);
        nowPlaying.requestInitialFocus();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
    }

    @Override
    protected void onStop() {
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (nowPlaying != null) nowPlaying.release();
        player.release();
        artwork.shutdown();
        io.shutdownNow();
    }
}
