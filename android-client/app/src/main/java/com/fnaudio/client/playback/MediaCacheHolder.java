package com.fnaudio.client.playback;

import android.content.Context;

import androidx.annotation.Nullable;
import androidx.media3.database.StandaloneDatabaseProvider;
import androidx.media3.datasource.cache.LeastRecentlyUsedCacheEvictor;
import androidx.media3.datasource.cache.SimpleCache;

import java.io.File;

/**
 * 进程内唯一的 {@link SimpleCache}（media3 不允许同一目录开两个实例）。
 *
 * <p>P2-2：断网可放的字节就存在这里。配额由调用方给，0 表示关闭。
 */
final class MediaCacheHolder {

    private static final String DIRECTORY = "media-cache";

    private static SimpleCache cache;

    private MediaCacheHolder() {
    }

    @Nullable
    static synchronized SimpleCache open(Context context, long maxBytes) {
        if (maxBytes <= 0) return null;
        if (cache != null) return cache;
        Context app = context.getApplicationContext();
        File directory = new File(app.getCacheDir(), DIRECTORY);
        if (!directory.exists() && !directory.mkdirs()) return null;
        try {
            cache = new SimpleCache(
                    directory,
                    new LeastRecentlyUsedCacheEvictor(maxBytes),
                    new StandaloneDatabaseProvider(app));
            return cache;
        } catch (Throwable unavailable) {
            // 缓存只是加速与离线能力：开不出来就退回纯网络播放，不该让播放器起不来。
            cache = null;
            return null;
        }
    }

    static synchronized long sizeBytes() {
        return cache == null ? 0 : cache.getCacheSpace();
    }

    static synchronized void release() {
        if (cache == null) return;
        try {
            cache.release();
        } catch (Throwable ignored) {
            // 释放失败只影响下次启动能否重建，不往上抛。
        }
        cache = null;
    }
}
