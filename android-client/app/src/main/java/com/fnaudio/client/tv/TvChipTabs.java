package com.fnaudio.client.tv;

import android.content.Context;
import android.graphics.Typeface;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * Secondary tab row: the library's 歌曲 / 专辑 / 艺术家, and 我的's two halves.
 *
 * <p>Deliberately lighter than {@link TvTabBar}: 40dp instead of 56dp, 14sp
 * instead of 18sp, and an accent underline instead of a filled pill, so a
 * viewer can tell "another level down" from "another page" at a glance. Both
 * reference clients use the same trick for their in-page tabs.
 */
final class TvChipTabs extends LinearLayout {
    interface OnSelected {
        void onSelected(int index);
    }

    private final List<View> chips = new ArrayList<>();
    private final List<TextView> labels = new ArrayList<>();
    private final List<View> underlines = new ArrayList<>();

    private OnSelected selectedListener;
    private int selected;

    TvChipTabs(Context context, String[] texts) {
        super(context);
        setOrientation(HORIZONTAL);
        setGravity(Gravity.CENTER_VERTICAL);
        setPadding(TvTheme.dp(context, TvTheme.SCREEN_EDGE), 0, 0, 0);
        setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(context, 40f)));

        for (int index = 0; index < texts.length; index++) {
            FrameLayout chip = new FrameLayout(context);
            chip.setFocusable(true);
            chip.setFocusableInTouchMode(false);
            chip.setDescendantFocusability(FOCUS_BLOCK_DESCENDANTS);
            chip.setPadding(TvTheme.dp(context, 14), 0, TvTheme.dp(context, 14), 0);
            chip.setForeground(TvTheme.focusRing(context, TvTheme.R_PILL));
            LinearLayout.LayoutParams chipParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT);
            if (index > 0) chipParams.leftMargin = TvTheme.dp(context, 6);
            chip.setLayoutParams(chipParams);

            TextView label = new TextView(context);
            label.setText(texts[index]);
            label.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_SUB);
            label.setGravity(Gravity.CENTER);
            label.setTextColor(TvTheme.TEXT_3);
            chip.addView(label, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

            // Fixed width, not MATCH_PARENT. A bare View with MATCH_PARENT inside
            // a WRAP_CONTENT FrameLayout is measured against the AT_MOST spec and
            // reports the whole remaining width, which made the first chip 1824px
            // wide and pushed the other two off screen.
            View underline = new View(context);
            underline.setBackgroundColor(TvTheme.ACCENT);
            underline.setVisibility(View.INVISIBLE);
            FrameLayout.LayoutParams lineParams = new FrameLayout.LayoutParams(
                    TvTheme.dp(context, 26f), TvTheme.dp(context, 3f),
                    Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
            lineParams.bottomMargin = TvTheme.dp(context, 4f);
            chip.addView(underline, lineParams);

            final int position = index;
            chip.setOnClickListener(view -> select(position, true));
            addView(chip);
            chips.add(chip);
            labels.add(label);
            underlines.add(underline);
        }
        select(0, false);
    }

    void setOnSelected(OnSelected value) {
        this.selectedListener = value;
    }

    int selected() {
        return selected;
    }

    void select(int index, boolean notify) {
        if (index < 0 || index >= chips.size()) return;
        selected = index;
        for (int position = 0; position < chips.size(); position++) {
            boolean active = position == index;
            labels.get(position).setTextColor(active ? TvTheme.TEXT : TvTheme.TEXT_3);
            labels.get(position).setTypeface(active ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
            underlines.get(position).setVisibility(active ? View.VISIBLE : View.INVISIBLE);
        }
        if (notify && selectedListener != null) selectedListener.onSelected(index);
    }

    View itemAt(int index) {
        return index >= 0 && index < chips.size() ? chips.get(index) : null;
    }

    void focusSelected() {
        View chip = itemAt(selected);
        if (chip != null) chip.requestFocus();
    }

    /**
     * Down from the chip row enters the page content.
     *
     * <p>Named differently from {@link View#setNextFocusDownId(int)} on purpose:
     * that one wires a single chip, this one wires the whole row, and shadowing
     * it with a different meaning is how focus bugs get written.
     */
    void setContentNextFocusDownId(int id) {
        for (View chip : chips) chip.setNextFocusDownId(id);
    }
}
