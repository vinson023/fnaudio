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
 * Top navigation bar: centred text tabs, 56dp tall.
 *
 * <p>Both reference clients put navigation at the top of the screen and left
 * the whole width to content; the legacy client's 136dp side rail cost 14% of
 * the viewport before anything was drawn. The bar is deliberately not a
 * {@code TabLayout}: that widget's indicator animation and touch affordances
 * (ripple, scroll edges) are phone idioms that need to be switched off again
 * one by one on a television.
 *
 * <p>Left and right move the highlight between tabs; the callback fires only on
 * OK, so brushing past a tab does not reload a page.
 */
final class TvTabBar extends LinearLayout {
    interface OnTabSelected {
        void onTabSelected(int index);
    }

    private final List<FrameLayout> items = new ArrayList<>();
    private final List<TextView> labels = new ArrayList<>();
    private final List<View> indicators = new ArrayList<>();

    private int selected;
    private OnTabSelected listener;

    TvTabBar(Context context, String[] titles) {
        super(context);
        setOrientation(HORIZONTAL);
        setGravity(Gravity.CENTER);
        setClipChildren(false);
        setClipToPadding(false);
        setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, TvTheme.dp(context, TvTheme.TAB_BAR_H)));

        for (int index = 0; index < titles.length; index++) {
            final int position = index;
            FrameLayout item = new FrameLayout(context);
            item.setFocusable(true);
            item.setFocusableInTouchMode(false);
            item.setClickable(true);
            // The focus belongs to the tab container, never to the label: with
            // the default descendant policy the request was handed to a child
            // that cannot hold focus, so returning from the content area
            // dropped the highlight entirely.
            item.setDescendantFocusability(FOCUS_BLOCK_DESCENDANTS);
            item.setForeground(TvTheme.focusRing(context, 10f));
            item.setClipChildren(false);
            LinearLayout.LayoutParams itemParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT);
            if (index > 0) itemParams.leftMargin = TvTheme.dp(context, 16);
            item.setLayoutParams(itemParams);

            TextView label = new TextView(context);
            label.setText(titles[index]);
            label.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.TAB);
            label.setTextColor(TvTheme.TEXT_3);
            label.setGravity(Gravity.CENTER);
            label.setPadding(TvTheme.dp(context, 16), 0, TvTheme.dp(context, 16), 0);
            label.setSingleLine(true);
            item.addView(label, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT));

            View indicator = new View(context);
            indicator.setBackground(TvTheme.rounded(context, TvTheme.ACCENT, 2f));
            indicator.setVisibility(INVISIBLE);
            FrameLayout.LayoutParams indicatorParams = new FrameLayout.LayoutParams(
                    0, TvTheme.dp(context, 3), Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
            indicatorParams.bottomMargin = TvTheme.dp(context, 10);
            item.addView(indicator, indicatorParams);
            final View measured = indicator;
            label.post(() -> {
                ViewGroup.LayoutParams params = measured.getLayoutParams();
                params.width = Math.max(TvTheme.dp(getContext(), 18),
                        Math.round(label.getWidth() * 0.72f));
                measured.setLayoutParams(params);
            });

            item.setOnClickListener(view -> select(position, true));
            item.setOnFocusChangeListener((view, hasFocus) -> {
                float scale = hasFocus ? TvTheme.FOCUS_SCALE : 1f;
                view.animate().scaleX(scale).scaleY(scale)
                        .setDuration(TvTheme.FOCUS_MS).start();
                label.setTextColor(hasFocus || position == selected
                        ? TvTheme.TEXT : TvTheme.TEXT_3);
                label.setTypeface(hasFocus || position == selected
                        ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
            });

            addView(item);
            items.add(item);
            labels.add(label);
            indicators.add(indicator);
        }
        select(0, false);
    }

    void setOnTabSelected(OnTabSelected value) {
        this.listener = value;
    }

    int selectedIndex() {
        return selected;
    }

    View itemAt(int index) {
        return index >= 0 && index < items.size() ? items.get(index) : null;
    }

    /** Moves the highlight and, when {@code notify} is set, tells the host. */
    void select(int index, boolean notify) {
        if (index < 0 || index >= items.size()) return;
        selected = index;
        for (int position = 0; position < items.size(); position++) {
            boolean active = position == index;
            indicators.get(position).setVisibility(active ? VISIBLE : INVISIBLE);
            TextView label = labels.get(position);
            label.setTextColor(active || items.get(position).isFocused()
                    ? TvTheme.TEXT : TvTheme.TEXT_3);
            label.setTypeface(active ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        }
        if (notify && listener != null) listener.onTabSelected(index);
    }

    /** Puts the highlight back on the active tab, used when leaving the content. */
    void focusSelected() {
        if (selected >= 0 && selected < items.size()) items.get(selected).requestFocus();
    }
}
