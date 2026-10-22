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
    private static final String RECOVERY_PAYLOAD = "payload.recovery.v1";
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
        store.upsert(remote.withFnConnectRelay(true), false);

        List<ConnectionProfile> profiles = store.list();
        assertTrue(profiles.stream().anyMatch(profile -> HOME_ID.equals(profile.id)));
        assertTrue(profiles.stream().anyMatch(profile -> REMOTE_ID.equals(profile.id)));
        assertEquals(HOME_ID, store.active().id);
        assertEquals("password-remote", store.find(REMOTE_ID).password);
        assertEquals("sha256/ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=", store.find(REMOTE_ID).certificatePinSha256);
        assertTrue(store.find(REMOTE_ID).fnConnectRelay);

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

    @Test
    public void unreadableCiphertextIsPreservedBeforeWritingNewHistory() {
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String original = preferences.getString(PAYLOAD, "");
        String originalRecovery = preferences.getString(RECOVERY_PAYLOAD, "");
        String corrupt = "not-a-valid-encrypted-profile-payload";
        try {
            preferences.edit().putString(PAYLOAD, corrupt).remove(RECOVERY_PAYLOAD).commit();
            SecureProfileStore damaged = new SecureProfileStore(context);
            assertTrue(damaged.list().isEmpty());

            damaged.upsert(ConnectionProfile.create(
                    "recovery-test", "恢复测试", "nas.test", 5666, false, false, "admin", "password"
            ), true);

            assertEquals(corrupt, preferences.getString(RECOVERY_PAYLOAD, ""));
            assertNotNull(damaged.find("recovery-test"));
        } finally {
            SharedPreferences.Editor restore = preferences.edit();
            if (original == null || original.isEmpty()) restore.remove(PAYLOAD);
            else restore.putString(PAYLOAD, original);
            if (originalRecovery == null || originalRecovery.isEmpty()) restore.remove(RECOVERY_PAYLOAD);
            else restore.putString(RECOVERY_PAYLOAD, originalRecovery);
            restore.commit();
            store = new SecureProfileStore(context);
        }
    }

    @Test
    public void oversizedCiphertextIsPreservedBeforeWritingNewHistory() {
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String original = preferences.getString(PAYLOAD, "");
        String originalRecovery = preferences.getString(RECOVERY_PAYLOAD, "");
        String oversized = new String(new char[1024 * 1024 + 1]).replace('\0', 'x');
        try {
            preferences.edit().putString(PAYLOAD, oversized).remove(RECOVERY_PAYLOAD).commit();
            SecureProfileStore damaged = new SecureProfileStore(context);
            assertTrue(damaged.list().isEmpty());

            damaged.upsert(ConnectionProfile.create(
                    "oversized-recovery-test", "超大恢复测试", "nas.test", 5666, false, false,
                    "admin", "password"
            ), true);

            assertEquals(oversized, preferences.getString(RECOVERY_PAYLOAD, ""));
            assertNotNull(damaged.find("oversized-recovery-test"));
        } finally {
            SharedPreferences.Editor restore = preferences.edit();
            if (original == null || original.isEmpty()) restore.remove(PAYLOAD);
            else restore.putString(PAYLOAD, original);
            if (originalRecovery == null || originalRecovery.isEmpty()) restore.remove(RECOVERY_PAYLOAD);
            else restore.putString(RECOVERY_PAYLOAD, originalRecovery);
            restore.commit();
            store = new SecureProfileStore(context);
        }
    }

    @Test
    public void oversizedNewStateDoesNotReplaceReadablePayload() {
        ConnectionProfile existing = ConnectionProfile.create(
                "existing-before-limit", "已有记录", "nas.test", 5666, false, false,
                "admin", "password"
        );
        store.upsert(existing, true);

        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String originalPayload = preferences.getString(PAYLOAD, "");
        String oversizedPassword = new String(new char[600 * 1024]).replace('\0', 'x');
        ConnectionProfile oversized = new ConnectionProfile(
                "oversized-new-state", "超大记录", "nas.test", 5666, false, false, "",
                "admin", oversizedPassword, "", "", 300L
        );

        try {
            store.upsert(oversized, false);
            throw new AssertionError("oversized state should be rejected before encryption");
        } catch (IllegalStateException expected) {
            assertNotNull(expected.getCause());
            assertTrue(expected.getCause().getMessage().contains("大小限制"));
        }

        assertEquals(originalPayload, preferences.getString(PAYLOAD, ""));
        assertNotNull(store.find(existing.id));
        assertTrue(store.find("oversized-new-state") == null);
    }

    private void removeTestProfiles() {
        for (String id : new String[]{HOME_ID, REMOTE_ID, FIRST_ID, SECOND_ID}) store.remove(id);
    }
}
