package com.fnaudio.client.playback;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import androidx.annotation.Nullable;

/** Bounded bitmap decode for untrusted remote artwork. */
final class ArtworkBitmapDecoder {
    static final long MAX_ARTWORK_PIXELS = 4L * 1024L * 1024L;

    private ArtworkBitmapDecoder() {
    }

    @Nullable
    static Bitmap decode(byte[] data) {
        if (data == null || data.length == 0) return null;
        try {
            BitmapFactory.Options bounds = new BitmapFactory.Options();
            bounds.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(data, 0, data.length, bounds);
            if (bounds.outWidth <= 0 || bounds.outHeight <= 0
                    || (long) bounds.outWidth * (long) bounds.outHeight > MAX_ARTWORK_PIXELS) {
                return null;
            }
            return BitmapFactory.decodeByteArray(data, 0, data.length);
        } catch (OutOfMemoryError error) {
            // A malformed or highly-compressed image can still exhaust the
            // native bitmap heap during decode. Convert it to a normal miss so
            // callers complete their future and retain the fallback glyph.
            return null;
        }
    }
}
