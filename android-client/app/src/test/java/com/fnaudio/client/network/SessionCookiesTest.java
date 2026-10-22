package com.fnaudio.client.network;

import org.junit.Test;
import java.lang.reflect.Method;
import static org.junit.Assert.assertEquals;

public final class SessionCookiesTest {
    @Test
    public void gatewayTokenPreservesBase64CookieOctets() throws Exception {
        Method encode = HttpClientFactory.class.getDeclaredMethod("encodeCookie", String.class);
        encode.setAccessible(true);
        assertEquals("abc+def/ghi==", encode.invoke(null, "abc+def/ghi=="));
    }
    @Test
    public void cookieDelimitersAndControlCharactersCannotInjectHeaders() {
        assertEquals("a%3Bb%0D%0A%20c", SessionCookies.encodeToken("a;b\r\n c"));
    }

    @Test
    public void gatewayRejectionBecomesAuthenticationFailure() {
        assertEquals(401, SessionCookies.responseStatus(200, " invalid token\n"));
        assertEquals(403, SessionCookies.responseStatus(403, "invalid token"));
        assertEquals(200, SessionCookies.responseStatus(200, "{\"title\":\"invalid token\"}"));
    }

    @Test
    public void accessCodeIsSentAsScopedGatewayHeaderValue() {
        assertEquals("ZGVtby1jb2Rl", SessionCookies.accessCodeHeader("demo-code"));
        assertEquals("", SessionCookies.accessCodeHeader("a\r\nb"));
    }

    @Test
    public void accessCodeCookieKeepsOnlySignedCookiePair() {
        assertEquals("os-access-code=signed-value",
                SessionCookies.accessCodeCookie(
                        "os-access-code=signed-value; Path=/; HttpOnly; SameSite=Lax"));
    }

    @Test
    public void accessCodeCookieIgnoresUnrelatedSetCookie() {
        assertEquals("", SessionCookies.accessCodeCookie("trim_token=token; Path=/"));
    }
}
