package com.fnaudio.client.data;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

@RunWith(AndroidJUnit4.class)
public final class SecureProfileStoreInstrumentedTest {
    private static final String PREFS = "fnaudio.secure.connections";
    private static final String PAYLOAD = "payload.v1";
    private static final String HOME_ID = "instrument-home";
    private static final String REMOTE_ID = "instrument-remote";
    private static final String FIRST_ID = "instrument-first";
    private static final String SECOND_ID = "instrument-second";

    private Context context;
    private SecureProfileStore store;
    private String originalActiveId;

    @Before
    public void setUp() {
        context = ApplicationProvider.getApplicationContext();
        store = new SecureProfileStore(context);
        ConnectionProfile active = store.active();
        originalActiveId = active == null ? "" : active.id;
        removeTestProfiles();
    }

    @After
    public void tearDown() {
        removeTestProfiles();
        store.setActive(originalActiveId);
    }

    @Test
    public void encryptedStoreKeepsMultipleProfilesAndActiveSelection() {
        ConnectionProfile home = new ConnectionProfile(
                HOME_ID, "家里的 NAS", "198.51.100.24", 5666, false, false, "",
                "admin", "test-password-home", "token-home", "long-home", 100L);
        ConnectionProfile remote = new ConnectionProfile(
                REMOTE_ID, "远程 NAS", "music.example.test", 5667, true, true,
                "sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=", "vinson",
                "password-remote", "token-remote", "long-remote", 200L);

        store.upsert(home, true);
        store.upsert(remote, false);

        List<ConnectionProfile> profiles = store.list();
        assertTrue(profiles.stream().anyMatch(profile -> HOME_ID.equals(profile.id)));
        assertTrue(profiles.stream().anyMatch(profile -> REMOTE_ID.equals(profile.id)));
        assertEquals(HOME_ID, store.active().id);
        assertEquals("password-remote", store.find(REMOTE_ID).password);
        assertEquals("sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=", store.find(REMOTE_ID).certificatePinSha256);

        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String encryptedPayload = preferences.getString(PAYLOAD, "");
        assertNotNull(encryptedPayload);
        assertFalse(encryptedPayload.isEmpty());
        assertFalse(encryptedPayload.contains("test-password-home"));
        assertFalse(encryptedPayload.contains("password-remote"));
    }

    @Test
    public void deletingActiveProfileClearsOnlyThatSelection() {
        ConnectionProfile first = ConnectionProfile.create(FIRST_ID, "第一台", "nas-one.test", 5666, false, false, "admin", "one");
        ConnectionProfile second = ConnectionProfile.create(SECOND_ID, "第二台", "nas-two.test", 5666, false, false, "admin", "two");
        store.upsert(first, true);
        store.upsert(second, false);

        store.remove(FIRST_ID);

        assertNotNull(store.find(SECOND_ID));
        assertTrue(store.find(FIRST_ID) == null);
        assertTrue(store.active() == null);
    }

    private void removeTestProfiles() {
        for (String id : new String[]{HOME_ID, REMOTE_ID, FIRST_ID, SECOND_ID}) store.remove(id);
    }
}
