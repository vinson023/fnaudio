package com.fnaudio.client.network;

import android.content.Context;
import android.content.SharedPreferences;

/** Persistent FN Connect routing preference, matching the fnOS client choices. */
public final class FnConnectSettings {
    public static final String MODE_SPEED = "speed";
    public static final String MODE_PUBLIC = "public";
    public static final String MODE_RELAY = "relay";

    private static final String PREFS = "fn_connect_settings";
    private static final String KEY_MODE = "mode";
    private static final String KEY_P2P_ENABLED = "p2p_enabled";

    private final SharedPreferences preferences;

    public FnConnectSettings(Context context) {
        preferences = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public String mode() {
        return normalizeMode(preferences.getString(KEY_MODE, MODE_SPEED));
    }

    public boolean isP2pEnabled() {
        return preferences.getBoolean(KEY_P2P_ENABLED, true);
    }

    public void save(String mode, boolean p2pEnabled) {
        preferences.edit().putString(KEY_MODE, normalizeMode(mode))
                .putBoolean(KEY_P2P_ENABLED, p2pEnabled).apply();
    }

    /** The profile stores the effective route so history restores predictably. */
    public String effectiveMode() {
        return isP2pEnabled() ? mode() : MODE_PUBLIC;
    }

    public static FnConnectResolver.Mode resolverMode(String mode) {
        String normalized = normalizeMode(mode);
        if (MODE_RELAY.equals(normalized)) return FnConnectResolver.Mode.RELAY;
        if (MODE_SPEED.equals(normalized)) return FnConnectResolver.Mode.AUTO;
        return FnConnectResolver.Mode.PUBLIC;
    }

    public static String normalizeMode(String value) {
        if (MODE_SPEED.equals(value) || MODE_PUBLIC.equals(value) || MODE_RELAY.equals(value)) return value;
        return MODE_SPEED;
    }

    public static String label(String mode) {
        switch (normalizeMode(mode)) {
            case MODE_RELAY: return "中继连接";
            case MODE_PUBLIC: return "公网连接";
            default: return "速度优先";
        }
    }
}
