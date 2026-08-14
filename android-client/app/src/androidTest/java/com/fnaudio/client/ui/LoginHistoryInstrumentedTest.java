package com.fnaudio.client.ui;

import android.content.Context;
import android.content.Intent;

import androidx.test.core.app.ActivityScenario;
import androidx.test.core.app.ApplicationProvider;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;

@RunWith(AndroidJUnit4.class)
public final class LoginHistoryInstrumentedTest {
    private static final String HOME_ID = "instrument-login-home";
    private static final String REMOTE_ID = "instrument-login-remote";

    private SecureProfileStore store;
    private String originalActiveId;

    @Before
    public void setUp() {
        Context context = ApplicationProvider.getApplicationContext();
        store = new SecureProfileStore(context);
        ConnectionProfile active = store.active();
        originalActiveId = active == null ? "" : active.id;
        removeTestProfiles();
        store.upsert(ConnectionProfile.create(HOME_ID, "家里的 NAS", "198.51.100.24", 5666, false, false, "admin", "test-saved-password"), true);
        store.upsert(ConnectionProfile.create(REMOTE_ID, "远程 NAS", "music.example.test", 5667, true, true, "vinson", ""), false);
    }

    @After
    public void tearDown() {
        removeTestProfiles();
        store.setActive(originalActiveId);
    }

    @Test
    public void loginStartsBlankAndHistoryScreenListsAllConnections() {
        Intent intent = new Intent(ApplicationProvider.getApplicationContext(), LoginActivity.class)
                .putExtra(LoginActivity.EXTRA_SKIP_AUTO_RESUME, true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try (ActivityScenario<LoginActivity> ignored = ActivityScenario.launch(intent)) {
            onView(withId(R.id.fnId)).check(matches(withText("")));
            onView(withId(R.id.host)).check(matches(withText("")));
            onView(withId(R.id.port)).check(matches(withText("5666")));
            onView(withId(R.id.password)).check(matches(withText("")));
            onView(withId(R.id.historyButton)).check(matches(isDisplayed()));
            onView(withId(R.id.historyButton)).perform(click());
            onView(withText("家里的 NAS")).check(matches(isDisplayed()));
            onView(withText("远程 NAS")).check(matches(isDisplayed()));
            onView(withText("http://198.51.100.24:5666")).check(matches(isDisplayed()));
            onView(withText("https://music.example.test:5667")).check(matches(isDisplayed()));
        }
    }

    private void removeTestProfiles() {
        store.remove(HOME_ID);
        store.remove(REMOTE_ID);
    }
}
