package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Typeface;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * The pairing card: code square, one sentence of instruction, the six digits.
 *
 * <p>280x330dp with a 220dp code, measured from the reference login screens.
 * The quiet zone is drawn into the bitmap rather than left to padding: a code
 * needs four modules of white on every side, and at this size that is more than
 * the card's own padding allows.
 *
 * <p>The card is focusable so a remote can press OK to get a fresh code after
 * the first one expires. The overlay follows the same four states as the
 * reference clients - waiting, expired, connecting, failed - because a card that
 * just sits there while the television is trying to reach a server reads as
 * broken.
 */
final class TvPairingCard extends FrameLayout {
    private final ImageView codeView;
    private final TextView hint;
    private final TextView digits;
    private final View overlay;
    private final TextView overlayText;

    private Runnable refreshListener;
    private boolean busy;

    TvPairingCard(Context context) {
        super(context);
        setFocusable(true);
        setFocusableInTouchMode(false);
        setBackground(TvTheme.rounded(context, TvTheme.CARD_FILL, TvTheme.R_CARD));
        setForeground(TvTheme.focusRing(context, TvTheme.R_CARD));
        setOnClickListener(view -> {
            if (busy) return;
            if (refreshListener != null) refreshListener.run();
        });

        LinearLayout column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setGravity(Gravity.CENTER_HORIZONTAL);
        column.setPadding(TvTheme.dp(context, 20), TvTheme.dp(context, 20),
                TvTheme.dp(context, 20), TvTheme.dp(context, 16));
        addView(column, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        codeView = new ImageView(context);
        codeView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        column.addView(codeView, new LinearLayout.LayoutParams(
                TvTheme.dp(context, 220), TvTheme.dp(context, 220)));

        hint = new TextView(context);
        hint.setText("用手机 fnAudio 扫码");
        hint.setTextColor(TvTheme.TEXT_2);
        hint.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_SUB);
        hint.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams hintParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        hintParams.topMargin = TvTheme.dp(context, 10);
        column.addView(hint, hintParams);

        digits = new TextView(context);
        digits.setTextColor(TvTheme.TEXT);
        digits.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24f);
        digits.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        digits.setLetterSpacing(0.18f);
        digits.setGravity(Gravity.CENTER);
        column.addView(digits);

        overlay = new View(context);
        overlay.setBackgroundColor(0xCD000000);
        overlay.setVisibility(GONE);
        addView(overlay, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        overlayText = new TextView(context);
        overlayText.setTextColor(TvTheme.TEXT);
        overlayText.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        overlayText.setGravity(Gravity.CENTER);
        overlayText.setLineSpacing(TvTheme.dp(context, 6), 1f);
        overlayText.setPadding(TvTheme.dp(context, 18), 0, TvTheme.dp(context, 18), 0);
        overlayText.setVisibility(GONE);
        addView(overlayText, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    void setOnRefresh(Runnable listener) {
        this.refreshListener = listener;
    }

    void setCode(String uri, String code) {
        busy = false;
        clearState();
        codeView.setImageBitmap(render(uri));
        digits.setText(spaced(code));
        hint.setText("用手机 fnAudio 扫码，或输入下面的码");
    }

    /** Nothing to show: no usable local address, so only the digits work. */
    void setUnavailable(String reason) {
        busy = true;
        codeView.setImageDrawable(null);
        digits.setText("");
        hint.setText(reason);
    }

    void showState(String message) {
        busy = true;
        overlay.setVisibility(VISIBLE);
        overlayText.setText(message);
        overlayText.setVisibility(VISIBLE);
    }

    void clearState() {
        overlay.setVisibility(GONE);
        overlayText.setVisibility(GONE);
    }

    /** Groups of three, which is how the same six digits are read out loud. */
    private static String spaced(String code) {
        if (code.length() != 6) return code;
        return code.substring(0, 3) + "  " + code.substring(3);
    }

    /**
     * Draws the matrix at a fixed module size with a four-module quiet zone.
     *
     * <p>Module edges are snapped to whole pixels: a fractional module boundary
     * blurs the pattern on a television panel that is already scaling it, and
     * cameras cope much worse with soft edges than with small ones.
     */
    private Bitmap render(String uri) {
        boolean[][] matrix = TvQrCode.encode(uri);
        int size = matrix.length;
        int quiet = 4;
        int total = size + quiet * 2;
        int target = Math.max(1, TvTheme.dp(getContext(), 220) / total);
        int pixels = total * target;
        Bitmap bitmap = Bitmap.createBitmap(pixels, pixels, Bitmap.Config.ARGB_8888);
        int[] row = new int[pixels];
        for (int y = 0; y < pixels; y++) {
            int matrixRow = y / target - quiet;
            for (int x = 0; x < pixels; x++) {
                boolean dark = false;
                if (matrixRow >= 0 && matrixRow < size) {
                    int matrixCol = x / target - quiet;
                    if (matrixCol >= 0 && matrixCol < size) dark = matrix[matrixRow][matrixCol];
                }
                row[x] = dark ? 0xFF000000 : 0xFFFFFFFF;
            }
            bitmap.setPixels(row, 0, pixels, 0, y, pixels, 1);
        }
        return bitmap;
    }
}
