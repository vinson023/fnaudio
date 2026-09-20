package com.fnaudio.client.network;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.lang.reflect.Method;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

@RunWith(AndroidJUnit4.class)
public final class FnOsAuthPayloadInstrumentedTest {
    @Test
    public void nestedTokenWinsOverSuccessfulOuterEnvelope() throws Exception {
        JSONObject response = new JSONObject(
                "{\"errno\":0,\"result\":\"succ\",\"data\":{\"token\":\"new-token\",\"longToken\":\"refresh\"}}"
        );
        Method method = FnOsAuthClient.class.getDeclaredMethod("findAuthPayload", JSONObject.class, int.class);
        method.setAccessible(true);

        JSONObject payload = (JSONObject) method.invoke(null, response, 0);

        assertEquals("new-token", payload.optString("token"));
        assertEquals("refresh", payload.optString("longToken"));
    }

    @Test
    public void envelopeRequestIdIsBoundWhenCredentialsAreNested() {
        assertTrue(FnOsAuthClient.requestIdMatches("current", "current", ""));
        assertTrue(FnOsAuthClient.requestIdMatches("current", "current", "current"));
        assertFalse(FnOsAuthClient.requestIdMatches("current", "stale", ""));
        assertFalse(FnOsAuthClient.requestIdMatches("current", "current", "stale"));
    }
}
