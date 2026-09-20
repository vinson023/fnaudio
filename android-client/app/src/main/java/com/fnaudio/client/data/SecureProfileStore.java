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
import java.util.Collections;
import java.util.Iterator;
import java.util.List;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class SecureProfileStore {
    private static final String PREFS = "fnaudio.secure.connections";
    private static final String PAYLOAD = "payload.v1";
    private static final String RECOVERY_PAYLOAD = "payload.recovery.v1";
    private static final String KEY_ALIAS = "fnaudio_connection_store_v1";
    private static final String ANDROID_KEY_STORE = "AndroidKeyStore";
    private static final int MAX_ENCRYPTED_PAYLOAD_CHARS = 1024 * 1024;
    private static final int MAX_CLEAR_PAYLOAD_BYTES = 512 * 1024;
    private static final int MAX_PROFILES = 128;
    // Stores are short lived and created by several activities/callbacks. The
    // encrypted payload is a read-modify-write record, so instance locks would
    // allow two stores to overwrite each other's profile changes.
    private static final Object STATE_LOCK = new Object();

    private final SharedPreferences preferences;
    private boolean unreadablePayload;
    private String unreadableCiphertext = "";

    public SecureProfileStore(Context context) {
        preferences = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public List<ConnectionProfile> list() {
        synchronized (STATE_LOCK) {
            return profilesFromState(readState());
        }
    }

    private List<ConnectionProfile> profilesFromState(JSONObject state) {
        JSONArray rows = state.optJSONArray("profiles");
        List<ConnectionProfile> profiles = new ArrayList<>();
        if (rows != null) {
            for (int i = 0; i < Math.min(rows.length(), MAX_PROFILES); i++) {
                JSONObject row = rows.optJSONObject(i);
                if (row != null) profiles.add(ConnectionProfile.fromJson(row));
            }
        }
        Collections.sort(profiles, (left, right) -> Long.compare(right.updatedAt, left.updatedAt));
        return profiles;
    }

    public ConnectionProfile active() {
        synchronized (STATE_LOCK) {
            JSONObject state = readState();
            String activeId = stringField(state, "activeId");
            for (ConnectionProfile profile : profilesFromState(state)) {
                if (profile.id.equals(activeId)) return profile;
            }
            return null;
        }
    }

    public ConnectionProfile find(String id) {
        synchronized (STATE_LOCK) {
            if (id == null) return null;
            for (ConnectionProfile profile : profilesFromState(readState())) {
                if (profile.id.equals(id)) return profile;
            }
            return null;
        }
    }

    public void upsert(ConnectionProfile profile, boolean makeActive) {
        synchronized (STATE_LOCK) {
            JSONObject state = readState();
            List<ConnectionProfile> profiles = profilesFromState(state);
            removeProfile(profiles, profile.id);
            profiles.add(profile);
            writeProfiles(state, profiles);
            if (makeActive) stateSafePut(state, "activeId", profile.id);
            writeState(state);
        }
    }

    public void setActive(String id) {
        synchronized (STATE_LOCK) {
            JSONObject state = readState();
            stateSafePut(state, "activeId", id == null ? "" : id);
            writeState(state);
        }
    }

    public void remove(String id) {
        synchronized (STATE_LOCK) {
            JSONObject state = readState();
            List<ConnectionProfile> profiles = profilesFromState(state);
            removeProfile(profiles, id);
            writeProfiles(state, profiles);
            if (id != null && id.equals(stringField(state, "activeId"))) stateSafePut(state, "activeId", "");
            writeState(state);
        }
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

    private static void removeProfile(List<ConnectionProfile> profiles, String id) {
        Iterator<ConnectionProfile> iterator = profiles.iterator();
        while (iterator.hasNext()) {
            if (iterator.next().id.equals(id)) iterator.remove();
        }
    }

    private JSONObject readState() {
        String encrypted = preferences.getString(PAYLOAD, "");
        if (encrypted == null || encrypted.isEmpty()) return new JSONObject();
        if (encrypted.length() > MAX_ENCRYPTED_PAYLOAD_CHARS) {
            unreadablePayload = true;
            // Keep the original value available for recovery just like any
            // other unreadable payload. A size guard must not turn into data loss.
            unreadableCiphertext = encrypted;
            return new JSONObject();
        }
        try {
            byte[] packed = Base64.decode(encrypted, Base64.NO_WRAP);
            if (packed.length < 13) throw new IllegalStateException("encrypted payload is truncated");
            int ivLength = packed[0] & 0xff;
            if (ivLength <= 0 || packed.length <= 1 + ivLength) throw new IllegalStateException("encrypted payload has an invalid IV");
            byte[] iv = new byte[ivLength];
            byte[] cipherText = new byte[packed.length - 1 - ivLength];
            System.arraycopy(packed, 1, iv, 0, ivLength);
            System.arraycopy(packed, 1 + ivLength, cipherText, 0, cipherText.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, secretKey(), new GCMParameterSpec(128, iv));
            byte[] clear = cipher.doFinal(cipherText);
            if (clear.length > MAX_CLEAR_PAYLOAD_BYTES) throw new IllegalStateException("encrypted payload is too large");
            JSONObject state = new JSONObject(new String(clear, StandardCharsets.UTF_8));
            unreadablePayload = false;
            unreadableCiphertext = "";
            return state;
        } catch (Exception ignored) {
            unreadablePayload = true;
            unreadableCiphertext = encrypted;
            return new JSONObject();
        }
    }

    private void writeState(JSONObject state) {
        try {
            byte[] clearPayload = state.toString().getBytes(StandardCharsets.UTF_8);
            // Enforce the same bound before encryption as readState enforces
            // after decryption. Otherwise a large record appears to save
            // successfully but becomes unreadable on the next access.
            if (clearPayload.length > MAX_CLEAR_PAYLOAD_BYTES) {
                throw new IllegalStateException("连接记录超过大小限制");
            }
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, secretKey());
            byte[] cipherText = cipher.doFinal(clearPayload);
            byte[] iv = cipher.getIV();
            byte[] packed = new byte[1 + iv.length + cipherText.length];
            packed[0] = (byte) iv.length;
            System.arraycopy(iv, 0, packed, 1, iv.length);
            System.arraycopy(cipherText, 0, packed, 1 + iv.length, cipherText.length);
            SharedPreferences.Editor editor = preferences.edit();
            // A KeyStore reset or payload corruption must not silently destroy
            // the only encrypted copy. Preserve it before accepting new state;
            // support can later recover it if the original key becomes usable.
            if (unreadablePayload && !unreadableCiphertext.isEmpty()) {
                editor.putString(RECOVERY_PAYLOAD, unreadableCiphertext);
            }
            editor.putString(PAYLOAD, Base64.encodeToString(packed, Base64.NO_WRAP)).apply();
            unreadablePayload = false;
            unreadableCiphertext = "";
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

    private static String stringField(JSONObject object, String key) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof String ? (String) value : "";
    }
}
