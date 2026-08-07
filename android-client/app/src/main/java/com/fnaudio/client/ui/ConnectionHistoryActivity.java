package com.fnaudio.client.ui;

import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;

import java.util.List;

public final class ConnectionHistoryActivity extends AppCompatActivity {
    public static final String EXTRA_PROFILE_ID = "profile_id";
    public static final int RESULT_EDIT_PROFILE = RESULT_FIRST_USER + 17;

    private SecureProfileStore store;
    private LinearLayout historyList;
    private TextView emptyText;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_connection_history);
        store = new SecureProfileStore(this);
        historyList = findViewById(R.id.historyList);
        emptyText = findViewById(R.id.historyEmptyText);
        findViewById(R.id.historyBackButton).setOnClickListener(view -> finish());
        renderHistory();
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderHistory();
    }

    private void renderHistory() {
        if (historyList == null || store == null) return;
        List<ConnectionProfile> profiles = store.list();
        historyList.removeAllViews();
        emptyText.setVisibility(profiles.isEmpty() ? View.VISIBLE : View.GONE);
        for (ConnectionProfile profile : profiles) historyList.addView(historyRow(profile));
    }

    private View historyRow(ConnectionProfile profile) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackgroundResource(R.drawable.history_item);
        card.setPadding(dp(16), dp(14), dp(12), dp(10));
        LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        cardParams.bottomMargin = dp(10);
        card.setLayoutParams(cardParams);

        TextView title = new TextView(this);
        title.setText(profile.name);
        title.setTextColor(getColor(R.color.fnaudio_text));
        title.setTextSize(17);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        card.addView(title);

        TextView endpoint = new TextView(this);
        endpoint.setText((profile.https ? "https://" : "http://") + profile.host + ":" + profile.port);
        endpoint.setTextColor(0xff64748b);
        endpoint.setTextSize(13);
        endpoint.setPadding(0, dp(4), 0, 0);
        endpoint.setMaxLines(1);
        card.addView(endpoint);

        TextView account = new TextView(this);
        account.setText("账号：" + profile.username + (profile.password.isEmpty() ? " · 未保存密码" : " · 密码已加密保存"));
        account.setTextColor(0xff64748b);
        account.setTextSize(12);
        account.setPadding(0, dp(3), 0, 0);
        account.setMaxLines(1);
        card.addView(account);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        actions.setPadding(0, dp(6), 0, 0);

        Button connect = compactButton("连接");
        connect.setTextColor(getColor(R.color.fnaudio_blue));
        connect.setOnClickListener(view -> returnProfile(profile, RESULT_OK));
        actions.addView(connect);

        Button edit = compactButton("编辑");
        edit.setOnClickListener(view -> returnProfile(profile, RESULT_EDIT_PROFILE));
        actions.addView(edit);

        Button remove = compactButton("删除");
        remove.setOnClickListener(view -> confirmDelete(profile));
        actions.addView(remove);
        card.addView(actions);

        card.setOnClickListener(view -> returnProfile(profile, RESULT_OK));
        return card;
    }

    private void returnProfile(ConnectionProfile profile, int resultCode) {
        Intent result = new Intent();
        result.putExtra(EXTRA_PROFILE_ID, profile.id);
        setResult(resultCode, result);
        finish();
    }

    private void confirmDelete(ConnectionProfile profile) {
        new AlertDialog.Builder(this)
                .setTitle("删除连接记录？")
                .setMessage("将删除本机加密保存的地址、账号、密码和登录令牌，不会更改 NAS。")
                .setNegativeButton("取消", null)
                .setPositiveButton("删除", (dialog, which) -> {
                    store.remove(profile.id);
                    renderHistory();
                })
                .show();
    }

    private Button compactButton(String text) {
        Button button = new Button(this, null, android.R.attr.borderlessButtonStyle);
        button.setText(text);
        button.setTextSize(13);
        button.setAllCaps(false);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setPadding(dp(12), 0, dp(12), 0);
        button.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, dp(42)));
        return button;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
