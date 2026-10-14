package com.fnaudio.client.playback;

import android.content.Context;
import android.graphics.Bitmap;
import android.net.Uri;
import android.webkit.CookieManager;

import androidx.annotation.OptIn;
import androidx.media3.common.util.BitmapLoader;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.session.SimpleBitmapLoader;

import com.fnaudio.client.data.ConnectionProfile;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.SettableFuture;

import java.io.File;
import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Collections;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;

/** Loads fnOS artwork with the authenticated client used by the media service. */
@OptIn(markerClass = UnstableApi.class)
public final class AuthenticatedBitmapLoader implements BitmapLoader {
    private static final int MAX_ARTWORK_BYTES = 8 * 1024 * 1024;
    private static final long MAX_CACHE_BYTES = 64L * 1024L * 1024L;
    private static final long MAX_CACHE_AGE_MS = 30L * 24L * 60L * 60L * 1000L;
    private static final long MAX_TEMP_FILE_AGE_MS = 24L * 60L * 60L * 1000L;
    private static final int MAX_PENDING_LOADS = 16;
    private static final Object ARTWORK_CACHE_LOCK = new Object();

    private final Context context;
    private final ConnectionProfile profile;
    private final OkHttpClient httpClient;
    private final SimpleBitmapLoader fallbackLoader = new SimpleBitmapLoader();
    private final ExecutorService executor = new ThreadPoolExecutor(
            1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(MAX_PENDING_LOADS),
            new ThreadPoolExecutor.AbortPolicy());
    private final File cacheDirectory;
    private final Object lifecycleLock = new Object();
    private final Set<SettableFuture<Bitmap>> pendingFutures = Collections.newSetFromMap(
            new ConcurrentHashMap<SettableFuture<Bitmap>, Boolean>());
    private final ConcurrentHashMap<SettableFuture<Bitmap>, Call> activeCalls = new ConcurrentHashMap<>();
    private boolean shutdown;

    public AuthenticatedBitmapLoader(Context context, ConnectionProfile profile, OkHttpClient httpClient) {
        this.context = context.getApplicationContext();
        this.profile = profile;
        this.httpClient = httpClient;
        this.cacheDirectory = new File(this.context.getFilesDir(), "media-artwork");
        try {
            // Cache maintenance is opportunistic and must not prevent the
            // playback service from starting when the bounded executor is
            // already shutting down or temporarily saturated.
            executor.execute(this::pruneCache);
        } catch (RejectedExecutionException ignored) {
            // Artwork loads still report their own lifecycle errors below.
        }
    }

    @Override
    public boolean supportsMimeType(String mimeType) {
        return fallbackLoader.supportsMimeType(mimeType);
    }

    @Override
    public ListenableFuture<Bitmap> decodeBitmap(byte[] data) {
        SettableFuture<Bitmap> future = SettableFuture.create();
        if (data == null || data.length == 0 || data.length > MAX_ARTWORK_BYTES) {
            future.setException(new IOException("Artwork data is empty or too large"));
            return future;
        }
        synchronized (lifecycleLock) {
            if (shutdown) {
                future.setException(new IOException("Artwork loader is shut down"));
                return future;
            }
            pendingFutures.add(future);
        }
        try {
            executor.execute(() -> {
                try {
                    if (future.isCancelled()) return;
                    Bitmap bitmap = ArtworkBitmapDecoder.decode(data);
                    if (bitmap == null) throw new IOException("Could not decode artwork");
                    if (!future.set(bitmap)) bitmap.recycle();
                } catch (Exception exception) {
                    future.setException(exception);
                } finally {
                    pendingFutures.remove(future);
                }
            });
        } catch (RejectedExecutionException exception) {
            pendingFutures.remove(future);
            future.setException(new IOException("Artwork loader is shut down", exception));
        }
        return future;
    }

    @Override
    public ListenableFuture<Bitmap> loadBitmap(Uri uri) {
        if (uri == null) return failedFuture("Artwork URI is missing");
        // Network artwork must remain on the active fnAudio origin. Letting an
        // arbitrary HTTP(S) URI fall through to SimpleBitmapLoader bypasses
        // this loader's byte/pixel limits and its cancellation lifecycle.
        if (!isAuthenticatedOrigin(uri)) {
            if (isHttpUri(uri)) return failedFuture("Artwork URI is outside the active server");
            return fallbackLoader.loadBitmap(uri);
        }
        SettableFuture<Bitmap> future = SettableFuture.create();
        synchronized (lifecycleLock) {
            if (shutdown) {
                future.setException(new IOException("Artwork loader is shut down"));
                return future;
            }
            pendingFutures.add(future);
        }
        // Media3 may cancel an artwork future when the notification/page no
        // longer needs it. Tie that cancellation to OkHttp as well, otherwise
        // a discarded image can keep downloading until the byte cap is hit.
        future.addListener(() -> {
            Call call = activeCalls.remove(future);
            if (call != null) call.cancel();
        }, Runnable::run);
        try {
            executor.execute(() -> {
                try {
                    if (future.isCancelled()) return;
                    byte[] data = readCached(uri);
                    if (data == null) {
                        data = download(uri, future);
                        if (future.isCancelled()) return;
                        if (data != null) writeCached(uri, data);
                    }
                    if (future.isCancelled()) return;
                    if (data == null || data.length == 0 || data.length > MAX_ARTWORK_BYTES) {
                        throw new IOException("Artwork response is empty or too large");
                    }
                    Bitmap bitmap = ArtworkBitmapDecoder.decode(data);
                    if (bitmap == null) throw new IOException("Could not decode artwork");
                    if (future.isCancelled()) {
                        bitmap.recycle();
                        return;
                    }
                    if (!future.set(bitmap)) bitmap.recycle();
                } catch (Exception exception) {
                    future.setException(exception);
                } finally {
                    pendingFutures.remove(future);
                }
            });
        } catch (RejectedExecutionException exception) {
            pendingFutures.remove(future);
            future.setException(new IOException("Artwork loader is shut down", exception));
        }
        return future;
    }

    public void shutdown() {
        synchronized (lifecycleLock) {
            if (shutdown) return;
            shutdown = true;
            for (SettableFuture<Bitmap> future : pendingFutures) {
                future.cancel(false);
            }
            pendingFutures.clear();
            for (Call call : activeCalls.values()) {
                call.cancel();
            }
            activeCalls.clear();
        }
        executor.shutdownNow();
    }

    private byte[] download(Uri uri, SettableFuture<Bitmap> future) throws IOException {
        Request.Builder request = new Request.Builder().url(uri.toString()).get();
        if (profile != null && !profile.webSession && !profile.token.isEmpty()) {
            String encodedToken;
            try {
                encodedToken = URLEncoder.encode(profile.token, StandardCharsets.UTF_8.name());
            } catch (Exception ignored) {
                encodedToken = profile.token;
            }
            request.header("Authorization", "Bearer " + profile.token)
                    .header("X-Fnaudio-Trim-Token", profile.token)
                    .header("Cookie", "fnaudio_trim_token=" + encodedToken + "; trim_token=" + encodedToken + "; token=" + encodedToken);
        } else if (profile != null && profile.webSession) {
            String cookie = CookieManager.getInstance().getCookie(uri.toString());
            if (cookie != null && !cookie.trim().isEmpty()) request.header("Cookie", cookie);
        }
        Call call = httpClient.newCall(request.build());
        activeCalls.put(future, call);
        if (future.isCancelled()) {
            activeCalls.remove(future, call);
            call.cancel();
            throw new IOException("Artwork request cancelled");
        }
        try (Response response = call.execute()) {
            if (!response.isSuccessful() || response.body() == null) {
                throw new IOException("Artwork response status " + response.code());
            }
            long length = response.body().contentLength();
            if (length > MAX_ARTWORK_BYTES) throw new IOException("Artwork response is too large");
            return readBoundedBody(response.body());
        } finally {
            activeCalls.remove(future, call);
        }
    }

    private static byte[] readBoundedBody(ResponseBody body) throws IOException {
        if (body == null) throw new IOException("Artwork response is empty");
        InputStream input = body.byteStream();
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int total = 0;
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (count == 0) continue;
            if (count > MAX_ARTWORK_BYTES - total) {
                throw new IOException("Artwork response is too large");
            }
            output.write(buffer, 0, count);
            total += count;
        }
        return output.toByteArray();
    }

    private byte[] readCached(Uri uri) {
        synchronized (ARTWORK_CACHE_LOCK) {
            File file = cacheFile(uri);
            long now = System.currentTimeMillis();
            if (!file.isFile()) return null;
            if (now - file.lastModified() > MAX_CACHE_AGE_MS) {
                // Keep expiry validation and deletion paired with atomic
                // replacement so an old loader cannot delete a fresh entry.
                //noinspection ResultOfMethodCallIgnored
                file.delete();
                return null;
            }
            // Touch before opening and keep it in the same lock as writers.
            // This prevents a read of an old descriptor from aging a newer
            // replacement entry.
            //noinspection ResultOfMethodCallIgnored
            file.setLastModified(now);
            try (FileInputStream input = new FileInputStream(file)) {
                // Size the buffer from the descriptor we will actually read,
                // not from a stale path lookup.
                long size = input.getChannel().size();
                if (size <= 0 || size > MAX_ARTWORK_BYTES) return null;
                byte[] data;
                try {
                    data = new byte[(int) size];
                } catch (OutOfMemoryError ignored) {
                    return null;
                }
                int offset = 0;
                while (offset < data.length) {
                    int count = input.read(data, offset, data.length - offset);
                    if (count < 0) return null;
                    if (count == 0) continue;
                    offset += count;
                }
                return data;
            } catch (IOException ignored) {
                return null;
            }
        }
    }

    private void writeCached(Uri uri, byte[] data) {
        if (data == null || data.length == 0 || data.length > MAX_ARTWORK_BYTES) return;
        // Keep the complete temporary-file/rename transaction inside the
        // lifecycle lock. Otherwise shutdown() can cancel the future between
        // the caller's last check and this rename, allowing an old service
        // instance to repopulate the shared cache after it was torn down.
        synchronized (lifecycleLock) {
            if (shutdown) return;
            if (!cacheDirectory.exists() && !cacheDirectory.mkdirs() && !cacheDirectory.isDirectory()) return;
            File target = cacheFile(uri);
            // PlaybackService replacement can briefly overlap an old loader while
            // both instances share this cache directory. A per-write temporary
            // name prevents either instance from deleting the other's artifact.
            File temporary = new File(cacheDirectory, target.getName() + ".tmp." + UUID.randomUUID());
            try (FileOutputStream output = new FileOutputStream(temporary)) {
                output.write(data);
                output.flush();
                synchronized (ARTWORK_CACHE_LOCK) {
                    if (shutdown || !temporary.renameTo(target)) {
                        // Never fall back to writing the target directly: an
                        // interrupted replacement must not destroy a valid entry.
                        //noinspection ResultOfMethodCallIgnored
                        temporary.delete();
                        return;
                    }
                    pruneCache();
                }
            } catch (IOException ignored) {
                // A cache miss must not prevent the notification from receiving the bitmap.
                //noinspection ResultOfMethodCallIgnored
                temporary.delete();
            }
        }
    }

    private File cacheFile(Uri uri) {
        // A URL alone is not an authorization boundary: two saved profiles
        // can point at the same server while representing different users.
        // Keep the profile identity inside the opaque filename digest so one
        // profile can never reuse another profile's authenticated artwork.
        String profileScope = profile == null ? "" : profile.id;
        return new File(cacheDirectory, sha256(profileScope.length() + ":" + profileScope + uri.toString()) + ".img");
    }

    private void pruneCache() {
        synchronized (ARTWORK_CACHE_LOCK) {
            File[] files = cacheDirectory.listFiles();
            if (files == null || files.length == 0) return;
            long now = System.currentTimeMillis();
            long total = 0L;
            for (File file : files) {
                boolean temporary = file.getName().contains(".tmp.");
                // Another loader instance may still be writing this file. Only
                // reclaim abandoned temporary files after a generous grace period.
                if (temporary) {
                    if (now - file.lastModified() > MAX_TEMP_FILE_AGE_MS) {
                        //noinspection ResultOfMethodCallIgnored
                        file.delete();
                    }
                    continue;
                }
                boolean expired = now - file.lastModified() > MAX_CACHE_AGE_MS;
                if (!file.isFile() || expired || file.length() <= 0 || file.length() > MAX_ARTWORK_BYTES) {
                    //noinspection ResultOfMethodCallIgnored
                    file.delete();
                } else {
                    total += file.length();
                }
            }
            if (total <= MAX_CACHE_BYTES) return;
            files = cacheDirectory.listFiles(file -> file.isFile() && file.getName().endsWith(".img"));
            if (files == null) return;
            Arrays.sort(files, new Comparator<File>() {
                @Override
                public int compare(File left, File right) {
                    return Long.compare(left.lastModified(), right.lastModified());
                }
            });
            for (File file : files) {
                if (total <= MAX_CACHE_BYTES) break;
                long length = file.length();
                if (file.delete()) total -= length;
            }
        }
    }

    private boolean isAuthenticatedOrigin(Uri uri) {
        if (profile == null || profile.host.isEmpty() || (!profile.webSession && profile.token.isEmpty())) return false;
        String expectedScheme = profile.https ? "https" : "http";
        if (!expectedScheme.equalsIgnoreCase(uri.getScheme()) || !profile.host.equalsIgnoreCase(uri.getHost())) return false;
        int defaultPort = profile.https ? 443 : 80;
        int expectedPort = profile.port > 0 ? profile.port : defaultPort;
        int actualPort = uri.getPort() < 0 ? defaultPort : uri.getPort();
        return expectedPort == actualPort;
    }

    private static boolean isHttpUri(Uri uri) {
        if (uri == null) return false;
        String scheme = uri.getScheme();
        return "http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme);
    }

    private static ListenableFuture<Bitmap> failedFuture(String message) {
        SettableFuture<Bitmap> future = SettableFuture.create();
        future.setException(new IOException(message));
        return future;
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder output = new StringBuilder(digest.length * 2);
            for (byte item : digest) output.append(String.format(Locale.ROOT, "%02x", item & 0xff));
            return output.toString();
        } catch (Exception ignored) {
            return Integer.toHexString(value.hashCode());
        }
    }
}
