package com.fnaudio.client.tv;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;

import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.HttpClientFactory;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * The television shell: a top tab bar, a full-width page area, and the
 * persistent playback bar.
 *
 * <p>Replaces the legacy screen, which spent 136dp of a 960dp viewport on a
 * vertical rail and stacked everything else into one Activity. Here navigation
 * is a 56dp bar across the top, pages swap inside the container, and the player
 * stays reachable without leaving the page.
 *
 * <p>Pages are plain Views rather than Fragments. A Fragment buys nothing on a
 * television: there is no swipe paging, no nested navigation and no state to
 * restore across process death, while its lifecycle adds two more places where
 * focus can be lost during a tab switch.
 */
public final class TvShellActivity extends Activity implements TvPlayer.Listener {
    public static final String EXTRA_PROFILE_ID = "com.fnaudio.client.tv.PROFILE_ID";

    private static final String[] TITLES = {"推荐", "资料库", "我的", "搜索", "设置"};

    private SecureProfileStore store;
    private ConnectionProfile profile;
    private TvApi api;
    private TvArtworkLoader artwork;
    private TvPlayer player;

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    private TvTabBar tabBar;
    private TvPlayerBar playerBar;
    private TvPlayerScreen playerScreen;
    private FrameLayout pageHost;
    private FrameLayout detailHost;
    @Nullable private TvDetailPage detailPage;
    /** Pages are kept, not rebuilt: switching tabs must not reset scroll or focus. */
    private final Map<Integer, View> pages = new HashMap<>();
    private boolean detailOpen;
    @Nullable private TvHomePage homePage;

    private int currentTab;

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
        artwork = new TvArtworkLoader(api, HttpClientFactory.create(this, profile));
        player = new TvPlayer(this, api);
        player.setListener(this);

        setContentView(buildRoot());
        TvUi.hideSystemBars(this);
        selectTab(0, false);
    }

    private ConnectionProfile resolveProfile() {
        String id = getIntent().getStringExtra(EXTRA_PROFILE_ID);
        if (id != null && !id.isEmpty()) {
            ConnectionProfile found = store.find(id);
            if (found != null) return found;
        }
        return store.active();
    }

    // ------------------------------------------------------------------ 布局

    private View buildRoot() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(TvTheme.BG);

        pageHost = new FrameLayout(this);
        pageHost.setClipChildren(false);
        root.addView(pageHost, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        detailHost = new FrameLayout(this);
        detailHost.setVisibility(View.GONE);
        root.addView(detailHost, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        tabBar = new TvTabBar(this, TITLES);
        tabBar.setOnTabSelected(index -> selectTab(index, true));
        root.addView(tabBar, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(this, TvTheme.TAB_BAR_H),
                Gravity.TOP));

        playerBar = new TvPlayerBar(this);
        playerBar.setOnAction(new TvPlayerBar.OnAction() {
            @Override public void onOpen() {
                openPlayerScreen();
            }

            @Override public void onNext() {
                player.next();
            }

            @Override public void onToggle() {
                player.toggle();
            }
        });
        playerBar.setVisibility(View.GONE);
        root.addView(playerBar, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(this, TvTheme.PLAYER_BAR_H),
                Gravity.BOTTOM));

        playerScreen = new TvPlayerScreen(this, player, api, artwork);
        playerScreen.setOnClose(this::closePlayerScreen);
        root.addView(playerScreen, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        applyInsets();
        return root;
    }

    /** Content starts below the tab bar and ends above the player when it shows. */
    private void applyInsets() {
        int top = TvTheme.dp(this, TvTheme.TAB_BAR_H + 24f);
        int bottom = playerBar.getVisibility() == View.VISIBLE
                ? TvTheme.dp(this, TvTheme.PLAYER_BAR_H) : TvTheme.dp(this, 24f);
        pageHost.setPadding(0, top, 0, bottom);
        detailHost.setPadding(0, top, 0, bottom);
    }

    private View placeholder(String title) {
        TextView view = new TextView(this);
        view.setText(title + " · 下一期实现");
        view.setTextColor(TvTheme.TEXT_4);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        view.setGravity(Gravity.CENTER);
        return view;
    }

    // ------------------------------------------------------------------ 页面

    private void selectTab(int index, boolean focusContent) {
        if (detailOpen) closeDetail(false);
        currentTab = index;
        tabBar.select(index, false);
        pageHost.removeAllViews();
        View page = pageFor(index);
        pageHost.addView(page, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        if (focusContent) focusPage(page);
    }

    private View pageFor(int index) {
        View cached = pages.get(index);
        if (cached != null) return cached;
        View page;
        switch (index) {
            case 0: page = createHomePage(); break;
            case 1: page = createLibraryPage(); break;
            case 2: page = createMinePage(); break;
            case 3: page = createSearchPage(); break;
            default: page = placeholder(TITLES[index]); break;
        }
        pages.put(index, page);
        return page;
    }

    private void focusPage(View page) {
        if (page instanceof TvHomePage) {
            ((TvHomePage) page).focusFirst();
        } else if (page instanceof TvLibraryPage) {
            ((TvLibraryPage) page).focusFirst();
        } else if (page instanceof TvMinePage) {
            ((TvMinePage) page).focusFirst();
        } else if (page instanceof TvSearchPage) {
            ((TvSearchPage) page).focusFirst();
        } else {
            tabBar.focusSelected();
        }
    }

    private View createHomePage() {
        homePage = new TvHomePage(this, artwork);
        homePage.setOnCardOpen(this::openCard);
        homePage.setOnTopEdge(this::focusTabs);
        homePage.showStatus("正在载入曲库…");

        io.execute(() -> {
            List<TvShelfData.Shelf> shelves = null;
            String failure = null;
            try {
                shelves = TvShelfData.build(api);
            } catch (IOException error) {
                failure = error.getMessage() == null ? "载入失败" : error.getMessage();
            }
            final List<TvShelfData.Shelf> loaded = shelves;
            final String error = failure;
            main.post(() -> {
                TvHomePage page = homePage;
                if (isFinishing() || page == null) return;
                if (loaded == null) {
                    page.showStatus("曲库载入失败\n" + error);
                    return;
                }
                TvApi.Track resume = player.current();
                page.render(loaded, resume, resume == null ? 0 : resumePercent());
                if (currentTab == 0 && !detailOpen) page.focusFirst();
            });
        });
        return homePage;
    }

    private View createLibraryPage() {
        TvLibraryPage page = new TvLibraryPage(this, api, artwork, io);
        page.setOnPlay((track, index, queue) -> playQueue(queue, index));
        page.setOnOpenCard(this::openDetail);
        page.setOnTopEdge(this::focusTabs);
        return page;
    }

    private View createMinePage() {
        TvMinePage page = new TvMinePage(this, api, artwork, io);
        page.setOnPlay((track, index, queue) -> playQueue(queue, index));
        page.setOnOpenCard(this::openDetail);
        page.setOnTopEdge(this::focusTabs);
        return page;
    }

    private View createSearchPage() {
        TvSearchPage page = new TvSearchPage(this, api, io);
        page.setOnPlay((track, index, queue) -> playQueue(queue, index));
        page.setOnTopEdge(this::focusTabs);
        return page;
    }

    private int resumePercent() {
        long duration = player.duration();
        if (duration <= 0) return 8;
        return (int) Math.max(4, Math.min(99, player.position() * 100 / duration));
    }

    /** Starts {@code queue} at {@code index} and shows the now-playing page. */
    private void playQueue(List<TvApi.Track> queue, int index) {
        if (queue == null || queue.isEmpty()) return;
        player.play(new ArrayList<>(queue), Math.max(0, index));
        openPlayerScreen();
    }

    /**
     * Covers the shell with the now-playing page.
     *
     * <p>The page and the bar go {@code INVISIBLE} rather than being covered
     * visually: an overlay that only paints on top still leaves a hundred
     * focusable cards underneath, and a remote's Up key will find them.
     */
    private void openPlayerScreen() {
        if (player.current() == null) return;
        pageHost.setVisibility(View.INVISIBLE);
        detailHost.setVisibility(View.INVISIBLE);
        playerBar.setVisibility(View.INVISIBLE);
        playerScreen.open();
    }

    private void closePlayerScreen() {
        pageHost.setVisibility(detailOpen ? View.INVISIBLE : View.VISIBLE);
        detailHost.setVisibility(detailOpen ? View.VISIBLE : View.GONE);
        playerBar.setVisibility(player.current() == null ? View.GONE : View.VISIBLE);
        if (detailOpen && detailPage != null) {
            detailPage.focusFirst();
        } else {
            focusPage(pageFor(currentTab));
        }
    }

    private void openCard(TvCardItem item) {
        if (item.track == null) {
            openDetail(item);
            return;
        }
        List<TvApi.Track> queue = item.queue.isEmpty()
                ? Collections.singletonList(item.track)
                : new ArrayList<>(item.queue);
        int start = 0;
        for (int index = 0; index < queue.size(); index++) {
            if (queue.get(index).id.equals(item.track.id)) {
                start = index;
                break;
            }
        }
        playQueue(queue, start);
    }

    /** Opens an album, artist or playlist on top of the current page. */
    private void openDetail(TvCardItem item) {
        if (item == null || item.id == null || item.id.isEmpty()) return;
        if (detailPage == null) {
            detailPage = new TvDetailPage(this, api, artwork, io);
            detailPage.setOnPlay((track, index, queue) -> playQueue(queue, index));
            detailPage.setOnBack(() -> closeDetail(true));
            detailHost.addView(detailPage, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        }
        detailOpen = true;
        pageHost.setVisibility(View.INVISIBLE);
        detailHost.setVisibility(View.VISIBLE);
        detailPage.open(item.id);
    }

    private void closeDetail(boolean restoreFocus) {
        detailOpen = false;
        detailHost.setVisibility(View.GONE);
        if (!playerScreen.isOpen()) pageHost.setVisibility(View.VISIBLE);
        if (restoreFocus) focusPage(pageFor(currentTab));
    }

    private void focusTabs() {
        View target = tabBar.itemAt(currentTab);
        if (target == null || !target.requestFocus()) tabBar.focusSelected();
    }

    // ------------------------------------------------------------- 播放回调

    @Override
    public void onTrackChanged(@Nullable TvApi.Track track, int index) {
        if (track == null) {
            playerBar.setVisibility(View.GONE);
            applyInsets();
            return;
        }
        if (playerBar.getVisibility() != View.INVISIBLE) playerBar.setVisibility(View.VISIBLE);
        playerBar.bind(track, artwork, player.isPlaying());
        applyInsets();
        playerScreen.onTrackChanged(track);
    }

    @Override
    public void onPlayingChanged(boolean playing) {
        playerBar.setPlaying(playing);
        playerScreen.onPlayingChanged(playing);
    }

    @Override
    public void onProgress(long positionMs, long durationMs) {
        playerBar.setProgress(positionMs, durationMs);
        playerScreen.onProgress(positionMs, durationMs);
    }

    @Override
    public void onQueueChanged() {
        playerScreen.onQueueChanged();
    }

    // ------------------------------------------------------------------ 按键

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (playerScreen != null && playerScreen.isOpen()
                && playerScreen.handleKey(keyCode, event)) {
            return true;
        }
        if (detailOpen && detailPage != null && detailPage.handleKey(keyCode, event)) {
            return true;
        }
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (isFocusInside(tabBar)) {
                if (currentTab != 0) {
                    selectTab(0, false);
                    tabBar.focusSelected();
                    return true;
                }
                return super.onKeyDown(keyCode, event);
            }
            tabBar.focusSelected();
            return true;
        }
        if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN && isFocusInside(tabBar)) {
            focusPage(pageFor(currentTab));
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    private boolean isFocusInside(View container) {
        View focus = getCurrentFocus();
        if (focus == null) return false;
        View parent = focus;
        while (parent != null) {
            if (parent == container) return true;
            if (!(parent.getParent() instanceof View)) return false;
            parent = (View) parent.getParent();
        }
        return false;
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        playerScreen.release();
        player.release();
        artwork.shutdown();
        io.shutdownNow();
    }
}
