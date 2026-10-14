package com.fnaudio.client.data;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import static org.junit.Assert.assertEquals;

@RunWith(AndroidJUnit4.class)
public final class ConnectionProfileInstrumentedTest {
    @Test
    public void malformedStoredPortUsesSchemeDefault() throws Exception {
        JSONObject json = new JSONObject()
                .put("host", "nas.example")
                .put("port", "not-a-port")
                .put("https", true);
        assertEquals(5667, ConnectionProfile.fromJson(json).port);
    }
}
