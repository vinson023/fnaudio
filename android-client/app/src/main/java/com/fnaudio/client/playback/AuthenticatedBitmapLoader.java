package com.fnaudio.client.playback;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;

import androidx.annotation.OptIn;
import androidx.media3.common.util.BitmapLoader;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.session.SimpleBitmapLoader;

import com.fnaudio.client.data.ConnectionProfile;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.SettableFuture;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

/** Loads fnOS artwork with the authenticated client used by the media service. */
@OptIn(markerClass = UnstableApi.class)
public final class AuthenticatedBitmapLoader implements BitmapLoader {
    private static final int MAX_ARTWORK_BYTES = 8 * 1024 * 1024;

    private final Context context;
    private final ConnectionProfile profile;
    private final OkHttpClient httpClient;
    private final SimpleBitmapLoader fallbackLoader = new SimpleBitmapLoader();
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final File cacheDirectory;

    public AuthenticatedBitmapLoader(Context context, ConnectionProfile profile, OkHttpClient httpClient) {
        this.context = context.getApplicationContext();
        this.profile = profile;
        this.httpClient = httpClient;
        this.cacheDirectory = new File(this.context.getFilesDir(), "media-artwork");
    }

    @Override
    public boolean supportsMimeType(String mimeType) {
        return fallbackLoader.supportsMimeType(mimeType);
    }

    @Override
    public ListenableFuture<Bitmap> decodeBitmap(byte[] data) {
        return fallbackLoader.decodeBitmap(data);
    }

    @Override
    public ListenableFuture<Bitmap> loadBitmap(Uri uri) {
        if (uri == null || !isAuthenticatedOrigin(uri)) return fallbackLoader.loadBitmap(uri);
        SettableFuture<Bitmap> future = SettableFuture.create();
        executor.execute(() -> {
            try {
                byte[] data = readCached(uri);
                if (data == null) {
                    data = download(uri);
                    if (data != null) writeCached(uri, data);
                }
                if (data == null || data.length == 0 || data.length > MAX_ARTWORK_BYTES) {
                    throw new IOException("Artwork response is empty or too large");
                }
                Bitmap bitmap = BitmapFactory.decodeByteArray(data, 0, data.length);
                if (bitmap == null) throw new IOException("Could not decode artwork");
                future.set(bitmap);
            } catch (Exception exception) {
                future.setException(exception);
            }
        });
        return future;
    }

    public void shutdown() {
        executor.shutdownNow();
    }

    private byte[] download(Uri uri) throws IOException {
        Request.Builder request = new Request.Builder().url(uri.toString()).get();
        if (profile != null && !profile.token.isEmpty()) {
            String encodedToken;
            try {
                encodedToken = URLEncoder.encode(profile.token, StandardCharsets.UTF_8.name());
            } catch (Exception ignored) {
                encodedToken = profile.token;
            }
            request.header("Authorization", "Bearer " + profile.token)
                    .header("X-Fnaudio-Trim-Token", profile.token)
                    .header("Cookie", "fnaudio_trim_token=" + encodedToken + "; trim_token=" + encodedToken + "; token=" + encodedToken);
        }
        try (Response response = httpClient.newCall(request.build()).execute()) {
            if (!response.isSuccessful() || response.body() == null) {
                throw new IOException("Artwork response status " + response.code());
            }
            long length = response.body().contentLength();
            if (length > MAX_ARTWORK_BYTES) throw new IOException("Artwork response is too large");
            return response.body().bytes();
        }
    }

    private byte[] readCached(Uri uri) {
        File file = cacheFile(uri);
        if (!file.isFile() || file.length() <= 0 || file.length() > MAX_ARTWORK_BYTES) return null;
        byte[] data = new byte[(int) file.length()];
        try (FileInputStream input = new FileInputStream(file)) {
            int offset = 0;
            while (offset < data.length) {
                int count = input.read(data, offset, data.length - offset);
                if (count < 0) return null;
                offset += count;
            }
            return data;
        } catch (IOException ignored) {
            return null;
        }
    }

    private void writeCached(Uri uri, byte[] data) {
        if (data == null || data.length == 0 || data.length > MAX_ARTWORK_BYTES) return;
        if (!cacheDirectory.exists() && !cacheDirectory.mkdirs() && !cacheDirectory.isDirectory()) return;
        File target = cacheFile(uri);
        File temporary = new File(cacheDirectory, target.getName() + ".tmp");
        try (FileOutputStream output = new FileOutputStream(temporary)) {
            output.write(data);
            output.flush();
            if (!temporary.renameTo(target)) {
                try (FileOutputStream direct = new FileOutputStream(target)) {
                    direct.write(data);
                }
                //noinspection ResultOfMethodCallIgnored
                temporary.delete();
            }
        } catch (IOException ignored) {
            // A cache miss must not prevent the notification from receiving the bitmap.
            //noinspection ResultOfMethodCallIgnored
            temporary.delete();
        }
    }

    private File cacheFile(Uri uri) {
        return new File(cacheDirectory, sha256(uri.toString()) + ".img");
    }

    private boolean isAuthenticatedOrigin(Uri uri) {
        if (profile == null || profile.host.isEmpty() || profile.token.isEmpty()) return false;
        String expectedScheme = profile.https ? "https" : "http";
        if (!expectedScheme.equalsIgnoreCase(uri.getScheme()) || !profile.host.equalsIgnoreCase(uri.getHost())) return false;
        int defaultPort = profile.https ? 443 : 80;
        int expectedPort = profile.port > 0 ? profile.port : defaultPort;
        int actualPort = uri.getPort() < 0 ? defaultPort : uri.getPort();
        return expectedPort == actualPort;
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
