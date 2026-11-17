package com.fnaudio.client.playback;

/**
 * 本地音频缓存的两条规则（P2-2）。
 *
 * <p>断网可放只能靠客户端缓存：NAS 不可达时服务端缓存形同虚设。这里只管"缓存什么"
 * 与"允许多大"，真正的读写交给 media3 的 {@code SimpleCache}。
 */
public final class MediaCachePolicy {

    /** 默认 1 GB。设置项落地前先用它。 */
    public static final long DEFAULT_MAX_BYTES = 1024L * 1024 * 1024L;
    public static final long MAX_MAX_BYTES = 8L * 1024 * 1024 * 1024L;

    private MediaCachePolicy() {
    }

    /**
     * 只缓存整段请求。
     *
     * <p>带 {@code start=} 的 URL 是中途续播（或 CUE 段），把它们的字节也写进缓存会让
     * 同一首歌碎成许多块：命中率低、还占双份空间。所以只认"从头开始"的请求。
     */
    public static boolean shouldCache(String url) {
        if (url == null || url.isEmpty()) return false;
        int queryAt = url.indexOf('?');
        if (queryAt < 0) return true;
        String query = url.substring(queryAt + 1);
        for (String pair : query.split("&")) {
            int eq = pair.indexOf('=');
            String key = eq < 0 ? pair : pair.substring(0, eq);
            if (!"start".equals(key)) continue;
            String value = eq < 0 ? "" : pair.substring(eq + 1);
            if (value.isEmpty()) continue;
            try {
                return Double.parseDouble(value) <= 0.0;
            } catch (NumberFormatException ignored) {
                return false;
            }
        }
        return true;
    }

    /** 0 表示关闭缓存；负数与超大值都夹回合理区间。 */
    public static long clampMaxBytes(long bytes) {
        if (bytes <= 0) return 0;
        return Math.min(bytes, MAX_MAX_BYTES);
    }
}
