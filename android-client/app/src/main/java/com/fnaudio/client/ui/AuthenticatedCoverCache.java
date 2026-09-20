package com.fnaudio.client.ui;

import android.content.Context;

import androidx.annotation.Nullable;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/** Small persistent cache for authenticated list thumbnails. */
final class AuthenticatedCoverCache {
    private static final long MAX_BYTES = 64L * 1024L * 1024L;
    private static final long MAX_TEMP_FILE_AGE_MS = 24L * 60L * 60L * 1000L;
    private static final int MAX_ENTRY_BYTES = 1024 * 1024;
    private static final int MAX_ENTRIES = 256;
    private static final int MAX_PENDING_WRITES = 24;
    private static final int MAX_KEY_CHARS = 4096;
    private static final Object CACHE_LOCK = new Object();
    private final File directory;
    private final ExecutorService writer = new ThreadPoolExecutor(
            1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(MAX_PENDING_WRITES),
            new ThreadPoolExecutor.AbortPolicy());

    AuthenticatedCoverCache(Context context) {
        directory = new File(context.getFilesDir(), "cover-thumbnails");
    }

    @Nullable InputStream open(String scope, String key) {
        if (!validKey(scope) || !validKey(key)) return null;
        File file = fileFor(scope, key);
        if (!file.isFile()) return null;
        synchronized (CACHE_LOCK) {
            FileInputStream input = null;
            try {
                input = new FileInputStream(file);
                // Validate the handle we will return, rather than a separate path
                // stat that can race an overlapping Activity cache replacement.
                long size = input.getChannel().size();
                if (size <= 0 || size > MAX_ENTRY_BYTES) {
                    input.close();
                    return null;
                }
                // Keep the recency update paired with the path lookup and the
                // writer's rename, so it cannot touch a replacement entry.
                file.setLastModified(System.currentTimeMillis());
                return input;
            } catch (IOException ignored) {
                if (input != null) {
                    try {
                        input.close();
                    } catch (IOException closeIgnored) {
                        // A failed cache read remains a normal cache miss.
                    }
                }
                return null;
            }
        }
    }

    void put(String scope, String key, byte[] body) {
        if (!validKey(scope) || !validKey(key) || body == null || body.length == 0 || body.length > MAX_ENTRY_BYTES) return;
        try {
            writer.execute(() -> write(scope, key, body));
        } catch (RejectedExecutionException ignored) {
            // Activity teardown can race a late WebView resource callback.
        }
    }

    void shutdown() {
        // Queued thumbnail writes only warm the Activity that requested them.
        // Drop work that has not started once that Activity is gone; an
        // in-flight atomic write is still allowed to cleanly finish.
        writer.shutdownNow();
    }

    private void write(String scope, String key, byte[] body) {
        if (!directory.exists() && !directory.mkdirs() && !directory.isDirectory()) return;
        File target = fileFor(scope, key);
        File temporary = new File(directory, target.getName() + ".tmp." + UUID.randomUUID());
        try (FileOutputStream output = new FileOutputStream(temporary)) {
            output.write(body);
            output.getFD().sync();
            synchronized (CACHE_LOCK) {
                if (!temporary.renameTo(target)) {
                    temporary.delete();
                    return;
                }
                trim();
            }
        } catch (IOException ignored) {
            temporary.delete();
        }
    }

    private File fileFor(String scope, String key) {
        // File names remain opaque; including the saved profile id prevents
        // authenticated images from crossing between profiles on one origin.
        return new File(directory, sha256(scope.length() + ":" + scope + key) + ".img");
    }

    private static boolean validKey(String key) {
        return key != null && !key.isEmpty() && key.length() <= MAX_KEY_CHARS;
    }

    private void trim() {
        File[] files = directory.listFiles();
        if (files == null) return;
        long now = System.currentTimeMillis();
        long total = 0;
        List<File> entries = new ArrayList<>();
        for (File file : files) {
            String name = file.getName();
            long length = file.length();
            if (name.contains(".tmp.")) {
                if (now - file.lastModified() > MAX_TEMP_FILE_AGE_MS) {
                    //noinspection ResultOfMethodCallIgnored
                    file.delete();
                }
                continue;
            }
            if (!file.isFile() || !name.endsWith(".img")
                    || length <= 0 || length > MAX_ENTRY_BYTES) {
                //noinspection ResultOfMethodCallIgnored
                file.delete();
                continue;
            }
            entries.add(file);
            total += length;
        }
        File[] ordered = entries.toArray(new File[0]);
        Arrays.sort(ordered, Comparator.comparingLong(File::lastModified));
        int remaining = ordered.length;
        for (File file : ordered) {
            if (total <= MAX_BYTES && remaining <= MAX_ENTRIES) break;
            long length = file.length();
            if (file.delete()) {
                total -= length;
                remaining--;
            }
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
