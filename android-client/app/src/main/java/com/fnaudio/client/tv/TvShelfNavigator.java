package com.fnaudio.client.tv;

import android.view.View;
import android.widget.ScrollView;

import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;

/**
 * Vertical movement between independent horizontal rows.
 *
 * <p>Each shelf is its own RecyclerView, so RecyclerView's own focus search
 * cannot cross from one row to the next: with no neighbouring item inside the
 * same list it simply stops at the edge. A television remote has up and down
 * and nothing else, so the page keeps an ordered registry of rows and moves the
 * focus itself, preserving the column index across the jump.
 *
 * <p>The column is clamped rather than remembered per row: moving down from a
 * long row into a shorter one and back is expected to land on the last item of
 * the short row, which is what every streaming client does.
 */
final class TvShelfNavigator {
    /** Called when a vertical move would leave the registered rows. */
    interface EdgeListener {
        boolean onVerticalEdge(RecyclerView from, int position, int direction);
    }

    private final List<RecyclerView> rows = new ArrayList<>();
    private ScrollView host;
    private int scrollTopInset = -1;
    private EdgeListener edge;
    private int lastRow;
    private int lastColumn;

    void attach(ScrollView scrollView, int topInsetPx) {
        this.host = scrollView;
        this.scrollTopInset = topInsetPx;
    }

    void setEdgeListener(EdgeListener listener) {
        this.edge = listener;
    }

    void register(RecyclerView row) {
        if (!rows.contains(row)) rows.add(row);
    }

    void clear() {
        rows.clear();
        edge = null;
        lastRow = 0;
        lastColumn = 0;
    }

    /** Column the viewer last stood on, so returning from the rail does not reset it. */
    int lastColumn() {
        return lastColumn;
    }

    /** Moves focus {@code direction} rows away from {@code from}, keeping the column. */
    boolean move(RecyclerView from, int position, int direction) {
        int index = rows.indexOf(from);
        if (index < 0) return false;
        int target = index + direction;
        if (target < 0 || target >= rows.size()) {
            return edge != null && edge.onVerticalEdge(from, position, direction);
        }
        return focusRow(target, position);
    }

    /** Jumps to an absolute row, used when the hero hands focus to the shelves. */
    boolean focusRow(int rowIndex, int position) {
        if (rowIndex < 0 || rowIndex >= rows.size()) return false;
        RecyclerView row = rows.get(rowIndex);
        RecyclerView.Adapter<?> adapter = row.getAdapter();
        if (adapter == null || adapter.getItemCount() == 0) return false;
        int column = Math.max(0, Math.min(position, adapter.getItemCount() - 1));
        lastRow = rowIndex;
        lastColumn = column;
        if (row.getLayoutManager() instanceof LinearLayoutManager) {
            ((LinearLayoutManager) row.getLayoutManager()).scrollToPositionWithOffset(column, 0);
        }
        row.post(() -> {
            RecyclerView.ViewHolder holder = row.findViewHolderForAdapterPosition(column);
            View target = holder != null ? holder.itemView : null;
            // A freshly scrolled row may not have bound the holder yet; falling
            // back to the first attached child keeps the focus somewhere inside
            // the row instead of letting it escape to nothing.
            if (target == null && row.getChildCount() > 0) target = row.getChildAt(0);
            if (target != null) target.requestFocus();
        });
        scrollHostTo(row);
        return true;
    }

    /**
     * Brings the whole row (including its heading) into view instead of letting
     * the ScrollView reveal only the focused tile, which on a 1080p screen left
     * the shelf heading cut in half.
     *
     * <p>The offset has to be accumulated through every intermediate container:
     * the shelves live inside a column that is the ScrollView's single child, so
     * the column's own {@code getTop()} is always zero and reading only that
     * scrolls nowhere — the first version did exactly this and focus landed on a
     * row that stayed off-screen.</p>
     */
    private void scrollHostTo(View row) {
        if (host == null) return;
        int top = 0;
        View node = row;
        while (node != null && node != host) {
            top += node.getTop();
            node = node.getParent() instanceof View ? (View) node.getParent() : null;
        }
        if (node != host) return;

        int viewport = host.getHeight() - host.getPaddingBottom();
        if (viewport <= 0) return;
        // Only move when the row is not already entirely in view, so handing
        // focus down one shelf does not yank the hero off screen.
        int current = host.getScrollY();
        int bottom = top + row.getHeight();
        int target;
        if (top - scrollTopInset < current) {
            target = top - scrollTopInset;
        } else if (bottom > current + viewport) {
            target = bottom - viewport + scrollTopInset;
        } else {
            return;
        }
        host.smoothScrollTo(0, Math.max(0, target));
    }
}
