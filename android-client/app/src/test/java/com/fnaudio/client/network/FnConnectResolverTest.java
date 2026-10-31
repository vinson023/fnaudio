package com.fnaudio.client.network;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public final class FnConnectResolverTest {
    @Test
    public void explicitHttpsSelectionDoesNotProbeOrFallBackToHttp() {
        java.util.List<FnConnectResolver.Endpoint> endpoints =
                FnConnectResolver.endpoints(5666, 5667, true);

        assertEquals(1, endpoints.size());
        assertTrue(endpoints.get(0).https);
        assertEquals(5667, endpoints.get(0).port);
    }

    @Test
    public void explicitHttpSelectionDoesNotProbeOrFallBackToHttps() {
        java.util.List<FnConnectResolver.Endpoint> endpoints =
                FnConnectResolver.endpoints(5666, 5667, false);

        assertEquals(1, endpoints.size());
        assertTrue(!endpoints.get(0).https);
        assertEquals(5666, endpoints.get(0).port);
    }
}
