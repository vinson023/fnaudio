package com.fnaudio.client.network;

import com.fnaudio.client.network.FnOsAuthClient.Attempt;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

/**
 * The login hop table and the errno wording, pinned to what fnOS 1.37.3 actually
 * answers.
 *
 * <p>Every number here was measured by replaying the WebSocket frames against a
 * real server (`docs/ANALYSIS_FNOS_LOGIN_ERRNO.md`, `artifacts/fnos-login-probe/`).
 * The point of the table test is the branch that is <em>absent</em>: a wrong
 * password must stop, not get retried as `user.login` + `username`, because that
 * frame is answered with errno 8192 and used to become the only message the user
 * ever saw.
 */
public final class FnOsAuthErrnoTest {

    @Test
    public void aRejectedPasswordIsReportedInsteadOfRetriedWithAnotherFieldName() {
        assertNull(
                "131072 means the credentials were rejected; swapping `user` for `username` cannot fix"
                        + " that and the swapped frame only answers 8192 (missing field), which is how a"
                        + " wrong password reached the user as \"错误码 8192\"",
                FnOsAuthClient.nextAttemptAfterFailure(
                        Attempt.LOGIN_USER, FnOsAuthClient.ERRNO_CREDENTIALS_REJECTED, false, true));
    }

    @Test
    public void theSwappedUserFieldOnlyRunsWhenFnOsDidNotRecogniseTheRequest() {
        assertEquals(Attempt.LOGIN_USERNAME, FnOsAuthClient.nextAttemptAfterFailure(
                Attempt.LOGIN_USER, FnOsAuthClient.ERRNO_UNKNOWN_REQUEST, false, true));
    }

    @Test
    public void aMissingFieldIsAlsoReportedRatherThanRetried() {
        assertNull(FnOsAuthClient.nextAttemptAfterFailure(
                Attempt.LOGIN_USER, FnOsAuthClient.ERRNO_MISSING_FIELD, false, true));
        assertNull(FnOsAuthClient.nextAttemptAfterFailure(Attempt.LOGIN_USER, 0, false, true));
    }

    @Test
    public void tokenHopsFallThroughOnlyWhenTheNextCredentialExists() {
        assertEquals(Attempt.LONG_TOKEN, FnOsAuthClient.nextAttemptAfterFailure(
                Attempt.AUTH_TOKEN, FnOsAuthClient.ERRNO_UNKNOWN_REQUEST, true, false));
        assertNull(FnOsAuthClient.nextAttemptAfterFailure(
                Attempt.AUTH_TOKEN, FnOsAuthClient.ERRNO_UNKNOWN_REQUEST, false, false));
        assertEquals(Attempt.LOGIN_USER, FnOsAuthClient.nextAttemptAfterFailure(
                Attempt.LONG_TOKEN, FnOsAuthClient.ERRNO_UNKNOWN_REQUEST, false, true));
        assertNull(FnOsAuthClient.nextAttemptAfterFailure(
                Attempt.LONG_TOKEN, FnOsAuthClient.ERRNO_UNKNOWN_REQUEST, false, false));
    }

    @Test
    public void theLastHopNeverLoops() {
        for (int errno : new int[] {0, FnOsAuthClient.ERRNO_MISSING_FIELD,
                FnOsAuthClient.ERRNO_CREDENTIALS_REJECTED, FnOsAuthClient.ERRNO_UNKNOWN_REQUEST}) {
            assertNull(FnOsAuthClient.nextAttemptAfterFailure(Attempt.LOGIN_USERNAME, errno, true, true));
        }
    }

    @Test
    public void everyMeasuredErrnoSaysSomethingTheUserCanActOn() {
        assertTrue(FnOsAuthClient.knownErrnoMessage(FnOsAuthClient.ERRNO_CREDENTIALS_REJECTED).contains("密码"));
        assertTrue(FnOsAuthClient.knownErrnoMessage(FnOsAuthClient.ERRNO_MISSING_FIELD).contains("缺少参数"));
        assertTrue(FnOsAuthClient.knownErrnoMessage(FnOsAuthClient.ERRNO_UNKNOWN_REQUEST).contains("不支持"));
    }

    @Test
    public void anUnmeasuredErrnoKeepsTheCallersOwnWording() {
        assertEquals("", FnOsAuthClient.knownErrnoMessage(0));
        assertEquals("", FnOsAuthClient.knownErrnoMessage(12345));
    }
}
