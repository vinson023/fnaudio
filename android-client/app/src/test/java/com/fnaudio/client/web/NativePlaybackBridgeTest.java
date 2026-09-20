package com.fnaudio.client.web;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.lang.reflect.Method;

import org.junit.Test;

public class NativePlaybackBridgeTest {
    @Test
    public void utf8BudgetCountsUnpairedSurrogatesAsReplacementBytes() throws Exception {
        Method method = NativePlaybackBridge.class.getDeclaredMethod(
                "boundedUtf8", String.class, int.class);
        method.setAccessible(true);

        String unpaired = new String(new char[] {'\uD800'});
        assertTrue((Boolean) method.invoke(null, unpaired, 3));
        assertFalse((Boolean) method.invoke(null, unpaired, 2));
    }
}
