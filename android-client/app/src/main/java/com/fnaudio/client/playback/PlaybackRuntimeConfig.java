package com.fnaudio.client.playback;

import androidx.annotation.Nullable;

import com.fnaudio.client.data.ConnectionProfile;

public final class PlaybackRuntimeConfig {
    private static volatile ConnectionProfile activeProfile;

    private PlaybackRuntimeConfig() {
    }

    public static synchronized boolean activate(ConnectionProfile profile) {
        boolean changed = activeProfile != null && !sameRuntimeConnection(activeProfile, profile);
        activeProfile = profile;
        return changed;
    }

    private static boolean sameRuntimeConnection(ConnectionProfile left, ConnectionProfile right) {
        if (left == right) return true;
        if (left == null || right == null) return false;
        return left.id.equals(right.id)
                && left.host.equals(right.host)
                && left.port == right.port
                && left.https == right.https
                && left.trustSelfSigned == right.trustSelfSigned
                && left.certificatePinSha256.equals(right.certificatePinSha256)
                && left.username.equals(right.username)
                && left.password.equals(right.password)
                && left.token.equals(right.token)
                && left.longToken.equals(right.longToken)
                && left.webSession == right.webSession;
    }

    @Nullable
    public static ConnectionProfile activeProfile() {
        return activeProfile;
    }
}
