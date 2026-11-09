package com.fnaudio.client.tv;

import static org.junit.Assert.assertNotNull;

import android.content.Context;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;

import org.junit.Test;
import org.junit.runner.RunWith;

/**
 * Seeds a connection profile that points at the local mock gateway.
 *
 * <p>An emulator has no way to type into the TV login form reliably: every
 * synthesized keystroke raises the soft keyboard, which covers the field below
 * it, so a scripted login is a race the form always wins. Writing the profile
 * through the same store the UI uses verifies the real persistence path and
 * leaves the shell free to simply launch {@code TvMainActivity}.
 *
 * <p>The store encrypts with an AndroidKeyStore key, so this cannot be done
 * with {@code adb push} or {@code run-as}; running inside the app process is
 * the only correct way.
 */
@RunWith(AndroidJUnit4.class)
public class TvMockSeedTest {
    private static final String HOST = "10.0.2.2";
    private static final int PORT = 18099;

    @Test
    public void seedLoopbackProfile() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        SecureProfileStore store = new SecureProfileStore(context);
        ConnectionProfile profile = ConnectionProfile.create(
                "tv-mock", "本地 mock", HOST, PORT, false, false, "tv", "tv");
        store.upsert(profile, true);
        assertNotNull(store.active());
        // SharedPreferences.apply() flushes asynchronously; the instrumentation
        // process is killed the moment this method returns, so without a pause
        // the seeded profile never reaches disk and the UI still shows "no
        // saved connections".
        Thread.sleep(2000);
    }
}
