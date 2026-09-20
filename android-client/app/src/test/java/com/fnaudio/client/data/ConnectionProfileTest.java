package com.fnaudio.client.data;

import org.json.JSONObject;
import org.junit.Test;

import static org.junit.Assert.assertEquals;

public final class ConnectionProfileTest {
    @Test
    public void invalidPortsUseSchemeDefaults() {
        assertEquals(5666, ConnectionProfile.create("", "", "nas.example", 0,
                false, false, "admin", "").port);
        assertEquals(5667, ConnectionProfile.create("", "", "nas.example", 70000,
                true, false, "admin", "").port);
        assertEquals(5666, ConnectionProfile.create("", "", "nas.example", -1,
                false, false, "admin", "").port);
    }

    @Test
    public void malformedStoredPortUsesSchemeDefault() throws Exception {
        JSONObject json = new JSONObject()
                .put("host", "nas.example")
                .put("port", "not-a-port")
                .put("https", true);
        assertEquals(5667, ConnectionProfile.fromJson(json).port);
    }

    @Test
    public void hostNormalizationDropsQueryFragmentAndUserinfo() {
        ConnectionProfile profile = ConnectionProfile.create(
                "", "", "HTTPS://NAS.Example:5667/music?view=all#top", 0,
                true, false, "admin", "");
        assertEquals("nas.example", profile.host);
        assertEquals("https://nas.example:5667", profile.httpOrigin());

        ConnectionProfile malformed = ConnectionProfile.create(
                "", "", "admin:secret@nas.example", 5666,
                false, false, "admin", "");
        assertEquals("", malformed.host);
    }
}
