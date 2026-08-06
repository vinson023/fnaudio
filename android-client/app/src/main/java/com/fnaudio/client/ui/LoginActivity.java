package com.fnaudio.client.ui;

import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.FnOsAuthClient;

import java.util.List;

public final class LoginActivity extends AppCompatActivity {
    private EditText profileName;
    private EditText host;
    private EditText port;
    private CheckBox useHttps;
    private CheckBox trustSelfSigned;
    private EditText username;
    private EditText password;
    private Button loginButton;
    private View progressRow;
    private TextView loginStatus;
    private View historySection;
    private LinearLayout historyList;

    private SecureProfileStore store;
    private final FnOsAuthClient authClient = new FnOsAuthClient();
    private String editingProfileId = "";
    private boolean busy;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);
        store = new SecureProfileStore(this);
        bindViews();
        renderHistory();

        ConnectionProfile active = store.active();
        if (active != null) fillForm(active);
        if (savedInstanceState == null && active != null && (!active.token.isEmpty() || !active.longToken.isEmpty())) {
            loginStatus.postDelayed(() -> resumeProfile(active), 220);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderHistory();
    }

    private void bindViews() {
        profileName = findViewById(R.id.profileName);
        host = findViewById(R.id.host);
        port = findViewById(R.id.port);
        useHttps = findViewById(R.id.useHttps);
        trustSelfSigned = findViewById(R.id.trustSelfSigned);
        username = findViewById(R.id.username);
        password = findViewById(R.id.password);
        loginButton = findViewById(R.id.loginButton);
        progressRow = findViewById(R.id.loginProgressRow);
        loginStatus = findViewById(R.id.loginStatus);
        historySection = findViewById(R.id.historySection);
        historyList = findViewById(R.id.historyList);

        port.setHint("端口号（HTTP 常用 5666，HTTPS 常用 5667）");
        loginButton.setOnClickListener(view -> loginWithPassword());
        useHttps.setOnCheckedChangeListener((button, checked) -> {
            trustSelfSigned.setEnabled(checked);
            if (port.getText().toString().trim().isEmpty()) port.setText(checked ? "5667" : "5666");
        });
        trustSelfSigned.setEnabled(useHttps.isChecked());
    }

    private void loginWithPassword() {
        ConnectionProfile profile = profileFromForm();
        if (profile == null) return;
        String clearPassword = password.getText().toString();
        if (clearPassword.isEmpty()) {
            password.setError("请输入密码");
            password.requestFocus();
            return;
        }
        authenticate(profile, clearPassword, "正在登录 fnOS…", false);
    }

    private void resumeProfile(ConnectionProfile profile) {
        if (busy) return;
        fillForm(profile);
        authenticate(profile, null, "正在恢复 “" + profile.name + "” 的登录…", true);
    }

    private void authenticate(ConnectionProfile profile, @Nullable String clearPassword, String status, boolean resume) {
        setBusy(true, status);
        hideKeyboard();
        authClient.authenticate(profile, clearPassword, new FnOsAuthClient.Callback() {
            @Override
            public void onSuccess(ConnectionProfile authenticatedProfile) {
                setBusy(false, "");
                password.setText("");
                store.upsert(authenticatedProfile, true);
                renderHistory();
                Intent intent = new Intent(LoginActivity.this, MainActivity.class);
                intent.putExtra(MainActivity.EXTRA_PROFILE_ID, authenticatedProfile.id);
                startActivity(intent);
            }

            @Override
            public void onError(String message) {
                setBusy(false, "");
                if (resume) {
                    fillForm(profile);
                    password.requestFocus();
                    Toast.makeText(LoginActivity.this, "登录已过期，请重新输入密码。", Toast.LENGTH_LONG).show();
                    showKeyboard(password);
                } else {
                    Toast.makeText(LoginActivity.this, message, Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    private ConnectionProfile profileFromForm() {
        String hostValue = host.getText().toString().trim();
        if (hostValue.isEmpty()) {
            host.setError("请输入网址或 IP 地址");
            host.requestFocus();
            return null;
        }
        String usernameValue = username.getText().toString().trim();
        if (usernameValue.isEmpty()) {
            username.setError("请输入飞牛账号");
            username.requestFocus();
            return null;
        }
        int portValue;
        try {
            String value = port.getText().toString().trim();
            portValue = value.isEmpty() ? (useHttps.isChecked() ? 5667 : 5666) : Integer.parseInt(value);
            if (portValue < 1 || portValue > 65535) throw new NumberFormatException();
        } catch (NumberFormatException exception) {
            port.setError("端口号必须在 1–65535 之间");
            port.requestFocus();
            return null;
        }
        return ConnectionProfile.create(
                editingProfileId,
                profileName.getText().toString(),
                hostValue,
                portValue,
                useHttps.isChecked(),
                trustSelfSigned.isChecked(),
                usernameValue
        );
    }

    private void fillForm(ConnectionProfile profile) {
        editingProfileId = profile.id;
        profileName.setText(profile.name);
        host.setText(profile.host);
        port.setText(String.valueOf(profile.port));
        useHttps.setChecked(profile.https);
        trustSelfSigned.setChecked(profile.trustSelfSigned);
        trustSelfSigned.setEnabled(profile.https);
        username.setText(profile.username);
        password.setText("");
    }

    private void renderHistory() {
        if (historyList == null || store == null) return;
        List<ConnectionProfile> profiles = store.list();
        historyList.removeAllViews();
        historySection.setVisibility(profiles.isEmpty() ? View.GONE : View.VISIBLE);
        for (ConnectionProfile profile : profiles) historyList.addView(historyRow(profile));
    }

    private View historyRow(ConnectionProfile profile) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setBackgroundResource(R.drawable.history_item);
        int padding = dp(14);
        row.setPadding(padding, dp(11), dp(8), dp(11));
        LinearLayout.LayoutParams rowParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        rowParams.topMargin = dp(8);
        row.setLayoutParams(rowParams);

        LinearLayout labels = new LinearLayout(this);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        TextView title = new TextView(this);
        title.setText(profile.name);
        title.setTextSize(15);
        title.setTextColor(getColor(R.color.fnaudio_text));
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        TextView detail = new TextView(this);
        detail.setText((profile.https ? "https://" : "http://") + profile.host + ":" + profile.port + " · " + profile.username);
        detail.setTextSize(12);
        detail.setTextColor(0xff64748b);
        detail.setMaxLines(1);
        labels.addView(title);
        labels.addView(detail);
        labels.setOnClickListener(view -> resumeProfile(profile));
        row.addView(labels);

        Button edit = compactButton("编辑");
        edit.setOnClickListener(view -> {
            fillForm(profile);
            host.requestFocus();
        });
        row.addView(edit);

        Button remove = compactButton("删除");
        remove.setOnClickListener(view -> new AlertDialog.Builder(this)
                .setTitle("删除连接记录？")
                .setMessage("只会删除本机保存的地址、账号和加密令牌，不会更改 NAS。")
                .setNegativeButton("取消", null)
                .setPositiveButton("删除", (dialog, which) -> {
                    store.remove(profile.id);
                    if (editingProfileId.equals(profile.id)) editingProfileId = "";
                    renderHistory();
                })
                .show());
        row.addView(remove);
        return row;
    }

    private Button compactButton(String text) {
        Button button = new Button(this, null, android.R.attr.borderlessButtonStyle);
        button.setText(text);
        button.setTextSize(12);
        button.setAllCaps(false);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setPadding(dp(8), 0, dp(8), 0);
        button.setLayoutParams(new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, dp(44)));
        return button;
    }

    private void setBusy(boolean value, String status) {
        busy = value;
        loginButton.setEnabled(!value);
        progressRow.setVisibility(value ? View.VISIBLE : View.GONE);
        loginStatus.setText(status);
        profileName.setEnabled(!value);
        host.setEnabled(!value);
        port.setEnabled(!value);
        useHttps.setEnabled(!value);
        trustSelfSigned.setEnabled(!value && useHttps.isChecked());
        username.setEnabled(!value);
        password.setEnabled(!value);
    }

    private void hideKeyboard() {
        View view = getCurrentFocus();
        if (view == null) return;
        InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
        manager.hideSoftInputFromWindow(view.getWindowToken(), 0);
    }

    private void showKeyboard(View view) {
        view.postDelayed(() -> {
            InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            manager.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT);
        }, 180);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
