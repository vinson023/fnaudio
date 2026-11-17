package com.fnaudio.client.playback;

import androidx.annotation.NonNull;
import androidx.media3.datasource.DataSink;
import androidx.media3.datasource.DataSpec;

import java.io.IOException;

/**
 * 只把"整段请求"写进缓存（P2-2）。
 *
 * <p>{@code CacheDataSource} 会在每个分片写入前调用这里的 {@code open}；带
 * {@code start=} 的续播请求直接跳过，否则同一首歌会被写成许多互不相干的小块。
 */
final class SelectiveCacheDataSinkFactory implements DataSink.Factory {

    private final DataSink.Factory delegate;

    SelectiveCacheDataSinkFactory(DataSink.Factory delegate) {
        this.delegate = delegate;
    }

    @NonNull
    @Override
    public DataSink createDataSink() {
        return new SelectiveDataSink(delegate.createDataSink());
    }

    private static final class SelectiveDataSink implements DataSink {

        private final DataSink delegate;
        private boolean opened;

        SelectiveDataSink(DataSink delegate) {
            this.delegate = delegate;
        }

        @Override
        public void open(@NonNull DataSpec dataSpec) throws IOException {
            opened = MediaCachePolicy.shouldCache(dataSpec.uri.toString());
            if (opened) delegate.open(dataSpec);
        }

        @Override
        public void write(@NonNull byte[] buffer, int offset, int length) throws IOException {
            if (opened) delegate.write(buffer, offset, length);
        }

        @Override
        public void close() throws IOException {
            if (!opened) return;
            opened = false;
            delegate.close();
        }
    }
}
