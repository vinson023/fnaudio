package com.fnaudio.client.network;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public final class FnConnectRelayConfigInstrumentedTest {
    @Test
    public void visitInfoMapsToTppsV2Config() throws Exception {
        JSONObject root = new JSONObject("{"
                + "\"code\":0,\"data\":{\"nasId\":\"nas-server-id\",\"applyServer\":{"
                + "\"ip\":\"203.0.113.7\",\"port\":7205,\"t\":\"relay-token\","
                + "\"s\":\"visit-secret\",\"protocol\":\"quic\",\"logLevel\":\"\","
                + "\"connectConfig\":{\"stunServer\":\"203.0.113.8:3478\"}}}}");

        JSONObject config = FnConnectRelayConfigClient.parseConfig("my-nas", root);

        assertEquals("relay-token", config.getString("token"));
        assertEquals("visit-secret", config.getString("visit_secret_key"));
        assertEquals("203.0.113.7", config.getString("server_host"));
        assertEquals(7205, config.getInt("server_port"));
        assertEquals("203.0.113.8:3478", config.getString("stun_server"));
        assertEquals("nas-server-id", config.getString("visit_server"));
        assertEquals("v-my-nas", config.getString("visitor_name"));
        assertEquals("error", config.getString("log_level"));
        assertTrue(config.getString("run_id").startsWith("p2pv2-"));
        assertFalse(config.has("r"));
    }

    @Test
    public void incompleteVisitInfoIsRejected() {
        JSONObject root = new JSONObject();
        assertThrows(Exception.class,
                () -> FnConnectRelayConfigClient.parseConfig("my-nas", root));
    }

    @Test
    public void visitorIdentityRejectsUntrustedFnId() throws Exception {
        JSONObject root = new JSONObject("{"
                + "\"code\":0,\"data\":{\"nasId\":\"nas-server-id\",\"applyServer\":{"
                + "\"ip\":\"203.0.113.7\",\"port\":7205,\"t\":\"relay-token\","
                + "\"s\":\"visit-secret\"}}}");

        assertThrows(Exception.class,
                () -> FnConnectRelayConfigClient.parseConfig("bad/id", root));
        assertThrows(Exception.class,
                () -> FnConnectRelayConfigClient.parseConfig("x".repeat(65), root));
    }
}
