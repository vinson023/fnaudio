package com.fnaudio.client.data;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class SecureProfileStore {
    private static final String PREFS = "fnaudio.secure.connections";
    private static final String PAYLOAD = "payload.v1";
    private static final String KEY_ALIAS = "fnaudio_connection_store_v1";
    private static final String ANDROID_KEY_STORE = "AndroidKeyStore";

    private final SharedPreferences preferences;

    public SecureProfileStore(Context context) {
        preferences = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized List<ConnectionProfile> list() {
        JSONObject state = readState();
        JSONArray rows = state.optJSONArray("profiles");
        List<ConnectionProfile> profiles = new ArrayList<>();
        if (rows != null) {
            for (int i = 0; i < rows.length(); i++) {
                JSONObject row = rows.optJSONObject(i);
                if (row != null) profiles.add(ConnectionProfile.fromJson(row));
            }
        }
        profiles.sort(Comparator.comparingLong((ConnectionProfile item) -> item.updatedAt).reversed());
        return profiles;
    }

    public synchronized ConnectionProfile active() {
        JSONObject state = readState();
        String activeId = state.optString("activeId");
        for (ConnectionProfile profile : list()) {
            if (profile.id.equals(activeId)) return profile;
        }
        return null;
    }

    public synchronized ConnectionProfile find(String id) {
        if (id == null) return null;
        for (ConnectionProfile profile : list()) {
            if (profile.id.equals(id)) return profile;
        }
        return null;
    }

    public synchronized void upsert(ConnectionProfile profile, boolean makeActive) {
        JSONObject state = readState();
        List<ConnectionProfile> profiles = list();
        profiles.removeIf(item -> item.id.equals(profile.id));
        profiles.add(profile);
        writeProfiles(state, profiles);
        if (makeActive) stateSafePut(state, "activeId", profile.id);
        writeState(state);
    }

    public synchronized void setActive(String id) {
        JSONObject state = readState();
        stateSafePut(state, "activeId", id == null ? "" : id);
        writeState(state);
    }

    public synchronized void remove(String id) {
        JSONObject state = readState();
        List<ConnectionProfile> profiles = list();
        profiles.removeIf(item -> item.id.equals(id));
        writeProfiles(state, profiles);
        if (id != null && id.equals(state.optString("activeId"))) stateSafePut(state, "activeId", "");
        writeState(state);
    }

    private void writeProfiles(JSONObject state, List<ConnectionProfile> profiles) {
        JSONArray rows = new JSONArray();
        for (ConnectionProfile profile : profiles) {
            try {
                rows.put(profile.toJson());
            } catch (Exception ignored) {
            }
        }
        stateSafePut(state, "profiles", rows);
    }

    private JSONObject readState() {
        String encrypted = preferences.getString(PAYLOAD, "");
        if (encrypted == null || encrypted.isEmpty()) return new JSONObject();
        try {
            byte[] packed = Base64.decode(encrypted, Base64.NO_WRAP);
            if (packed.length < 13) return new JSONObject();
            int ivLength = packed[0] & 0xff;
            if (ivLength <= 0 || packed.length <= 1 + ivLength) return new JSONObject();
            byte[] iv = new byte[ivLength];
            byte[] cipherText = new byte[packed.length - 1 - ivLength];
            System.arraycopy(packed, 1, iv, 0, ivLength);
            System.arraycopy(packed, 1 + ivLength, cipherText, 0, cipherText.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, secretKey(), new GCMParameterSpec(128, iv));
            byte[] clear = cipher.doFinal(cipherText);
            return new JSONObject(new String(clear, StandardCharsets.UTF_8));
        } catch (Exception ignored) {
            return new JSONObject();
        }
    }

    private void writeState(JSONObject state) {
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, secretKey());
            byte[] cipherText = cipher.doFinal(state.toString().getBytes(StandardCharsets.UTF_8));
            byte[] iv = cipher.getIV();
            byte[] packed = new byte[1 + iv.length + cipherText.length];
            packed[0] = (byte) iv.length;
            System.arraycopy(iv, 0, packed, 1, iv.length);
            System.arraycopy(cipherText, 0, packed, 1 + iv.length, cipherText.length);
            preferences.edit().putString(PAYLOAD, Base64.encodeToString(packed, Base64.NO_WRAP)).apply();
        } catch (Exception exception) {
            throw new IllegalStateException("无法安全保存连接记录", exception);
        }
    }

    private SecretKey secretKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance(ANDROID_KEY_STORE);
        keyStore.load(null);
        KeyStore.Entry entry = keyStore.getEntry(KEY_ALIAS, null);
        if (entry instanceof KeyStore.SecretKeyEntry) {
            return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEY_STORE);
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    private static void stateSafePut(JSONObject state, String key, Object value) {
        try {
            state.put(key, value);
        } catch (Exception ignored) {
        }
    }
}
