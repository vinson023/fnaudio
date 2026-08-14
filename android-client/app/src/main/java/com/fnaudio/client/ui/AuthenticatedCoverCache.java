package com.fnaudio.client.ui;

import android.content.Context;

import androidx.annotation.Nullable;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;

/** Small persistent cache for authenticated list thumbnails. */
final class AuthenticatedCoverCache {
    private static final long MAX_BYTES = 64L * 1024L * 1024L;
    private static final int MAX_ENTRY_BYTES = 1024 * 1024;
    private final File directory;

    AuthenticatedCoverCache(Context context) {
        directory = new File(context.getFilesDir(), "cover-thumbnails");
    }

    @Nullable InputStream open(String key) {
        File file = fileFor(key);
        if (!file.isFile() || file.length() <= 0 || file.length() > MAX_ENTRY_BYTES) return null;
        try {
            file.setLastModified(System.currentTimeMillis());
            return new FileInputStream(file);
        } catch (IOException ignored) {
            return null;
        }
    }

    void put(String key, byte[] body) {
        if (body == null || body.length == 0 || body.length > MAX_ENTRY_BYTES) return;
        if (!directory.exists() && !directory.mkdirs() && !directory.isDirectory()) return;
        File target = fileFor(key);
        File temporary = new File(directory, target.getName() + ".tmp");
        try (FileOutputStream output = new FileOutputStream(temporary)) {
            output.write(body);
            output.getFD().sync();
            if (!temporary.renameTo(target)) {
                temporary.delete();
                return;
            }
            trim();
        } catch (IOException ignored) {
            temporary.delete();
        }
    }

    private File fileFor(String key) {
        return new File(directory, sha256(key) + ".img");
    }

    private void trim() {
        File[] files = directory.listFiles((dir, name) -> name.endsWith(".img"));
        if (files == null) return;
        long total = 0;
        for (File file : files) total += file.length();
        while (total > MAX_BYTES && files.length > 0) {
            File oldest = files[0];
            for (File file : files) if (file.lastModified() < oldest.lastModified()) oldest = file;
            total -= oldest.length();
            oldest.delete();
            File[] next = directory.listFiles((dir, name) -> name.endsWith(".img"));
            files = next == null ? new File[0] : next;
        }
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(digest.length * 2);
            for (byte item : digest) result.append(String.format("%02x", item & 0xff));
            return result.toString();
        } catch (Exception error) {
            return Integer.toHexString(value.hashCode());
        }
    }
}
