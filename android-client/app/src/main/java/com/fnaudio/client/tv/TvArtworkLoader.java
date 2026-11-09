package com.fnaudio.client.tv;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.util.LruCache;
import android.widget.ImageView;

import androidx.annotation.Nullable;

import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * Cover-art loader for the TV shelves.
 *
 * <p>RecyclerView recycles rows on every scroll, so a request that lands after
 * its row was rebound must not paint onto the new row: the target keeps its
 * requested URL in the view tag and a late result is compared against it.
 *
 * <p>Covers are always requested at the largest size the shelf needs and
 * downsampled here, so one bitmap serves the 180dp card and the hero.
 */
final class TvArtworkLoader {
    private static final int SAMPLE_TARGET_PX = 512;
    private static final int HERO_TARGET_PX = 1280;

    private final TvApi api;
    private final OkHttpClient client;
    private final LruCache<String, Bitmap> memory;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService pool;

    TvArtworkLoader(TvApi api, OkHttpClient client) {
        this.api = api;
        this.client = client;
        int cacheKb = (int) (Runtime.getRuntime().maxMemory() / 1024 / 8);
        this.memory = new LruCache<String, Bitmap>(cacheKb) {
            @Override protected int sizeOf(String key, Bitmap value) {
                return value.getByteCount() / 1024;
            }
        };
        this.pool = Executors.newFixedThreadPool(4, new ThreadFactory() {
            private int index;

            @Override public Thread newThread(Runnable runnable) {
                Thread thread = new Thread(runnable, "tv-artwork-" + (index++));
                thread.setPriority(Thread.MIN_PRIORITY);
                thread.setDaemon(true);
                return thread;
            }
        });
    }

    /** Binds {@code coverKey} onto {@code target}; an empty key clears it. */
    void load(String coverKey, ImageView target) {
        loadInto(coverKey, target, SAMPLE_TARGET_PX);
    }

    /** Hero backdrop: one large request instead of upscaling the shelf copy. */
    void loadHires(String coverKey, ImageView target) {
        loadInto(coverKey, target, HERO_TARGET_PX);
    }

    private void loadInto(String coverKey, ImageView target, int sizePx) {
        if (coverKey == null || coverKey.isEmpty()) {
            target.setTag(coverKey);
            target.setImageDrawable(null);
            return;
        }
        String url = api.coverUrl(coverKey, sizePx);
        target.setTag(url);
        Bitmap cached = memory.get(url);
        if (cached != null) {
            target.setImageBitmap(cached);
            return;
        }
        target.setImageDrawable(null);
        pool.execute(() -> {
            Bitmap bitmap = fetch(url, sizePx);
            if (bitmap == null) return;
            memory.put(url, bitmap);
            main.post(() -> {
                if (url.equals(target.getTag())) target.setImageBitmap(bitmap);
            });
        });
    }

    @Nullable
    private Bitmap fetch(String url, int targetPx) {
        Request.Builder builder = new Request.Builder().url(url).get();
        api.authorize(builder);
        Response response = null;
        try {
            response = client.newCall(builder.build()).execute();
            if (!response.isSuccessful()) return null;
            ResponseBody body = response.body();
            if (body == null) return null;
            byte[] bytes = body.bytes();
            if (bytes.length == 0) return null;
            BitmapFactory.Options bounds = new BitmapFactory.Options();
            bounds.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(bytes, 0, bytes.length, bounds);
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight, targetPx);
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
        } catch (IOException | OutOfMemoryError ignored) {
            return null;
        } finally {
            if (response != null) response.close();
        }
    }

    private static int sampleSize(int width, int height, int targetPx) {
        int longest = Math.max(width, height);
        int sample = 1;
        while (longest / sample > targetPx * 2) sample *= 2;
        return sample;
    }

    void shutdown() {
        pool.shutdownNow();
        memory.evictAll();
    }
}
