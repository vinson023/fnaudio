package com.fnaudio.client.network;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public final class FnConnectSettingsTest {
    @Test
    public void routeModesMapToTheExpectedResolverMode() {
        assertEquals(FnConnectResolver.Mode.AUTO, FnConnectSettings.resolverMode(FnConnectSettings.MODE_SPEED));
        assertEquals(FnConnectResolver.Mode.PUBLIC, FnConnectSettings.resolverMode(FnConnectSettings.MODE_PUBLIC));
        assertEquals(FnConnectResolver.Mode.RELAY, FnConnectSettings.resolverMode(FnConnectSettings.MODE_RELAY));
    }

    @Test
    public void invalidStoredRouteFallsBackToSpeedPriority() {
        assertEquals(FnConnectSettings.MODE_SPEED, FnConnectSettings.normalizeMode("unknown"));
        assertEquals("速度优先", FnConnectSettings.label("unknown"));
    }
}
