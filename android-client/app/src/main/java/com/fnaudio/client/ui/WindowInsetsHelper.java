package com.fnaudio.client.ui;

import android.view.View;

import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

final class WindowInsetsHelper {
    private WindowInsetsHelper() {
    }

    static void applySafePadding(View root) {
        if (root == null) return;
        int left = root.getPaddingLeft();
        int top = root.getPaddingTop();
        int right = root.getPaddingRight();
        int bottom = root.getPaddingBottom();
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, windowInsets) -> {
            Insets safe = windowInsets.getInsets(
                    WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            view.setPadding(
                    left + safe.left,
                    top + safe.top,
                    right + safe.right,
                    bottom + safe.bottom
            );
            return windowInsets;
        });
        ViewCompat.requestApplyInsets(root);
    }
}
