package com.fnaudio.client.ui;

import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.FnOsAuthClient;

public final class LoginActivity extends AppCompatActivity {
    private static final int REQUEST_HISTORY = 701;

    private EditText profileName;
    private EditText host;
    private EditText port;
    private CheckBox useHttps;
    private CheckBox trustSelfSigned;
    private EditText username;
    private EditText password;
    private CheckBox savePassword;
    private Button loginButton;
    private Button historyButton;
    private View progressRow;
    private TextView loginStatus;

    private SecureProfileStore store;
    private final FnOsAuthClient authClient = new FnOsAuthClient();
    private String editingProfileId = "";
    private boolean busy;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureSystemBars();
        setContentView(R.layout.activity_login);
        WindowInsetsHelper.applySafePadding(findViewById(R.id.loginRoot));
        store = new SecureProfileStore(this);
        bindViews();
        renderHistoryButton();

        ConnectionProfile active = store.active();
        if (active != null) fillForm(active);
        if (savedInstanceState == null && active != null && (!active.token.isEmpty() || !active.longToken.isEmpty())) {
            loginStatus.postDelayed(() -> resumeProfile(active), 220);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderHistoryButton();
    }

    private void bindViews() {
        profileName = findViewById(R.id.profileName);
        host = findViewById(R.id.host);
        port = findViewById(R.id.port);
        useHttps = findViewById(R.id.useHttps);
        trustSelfSigned = findViewById(R.id.trustSelfSigned);
        username = findViewById(R.id.username);
        password = findViewById(R.id.password);
        savePassword = findViewById(R.id.savePassword);
        loginButton = findViewById(R.id.loginButton);
        historyButton = findViewById(R.id.historyButton);
        progressRow = findViewById(R.id.loginProgressRow);
        loginStatus = findViewById(R.id.loginStatus);

        if (port.getText().toString().trim().isEmpty()) port.setText("5666");
        loginButton.setOnClickListener(view -> loginWithPassword());
        historyButton.setOnClickListener(view -> startActivityForResult(
                new Intent(this, ConnectionHistoryActivity.class), REQUEST_HISTORY));
        useHttps.setOnCheckedChangeListener((button, checked) -> {
            trustSelfSigned.setEnabled(checked);
            String currentPort = port.getText().toString().trim();
            if (currentPort.isEmpty() || (!checked && "5667".equals(currentPort)) || (checked && "5666".equals(currentPort))) {
                port.setText(checked ? "5667" : "5666");
            }
        });
        trustSelfSigned.setEnabled(useHttps.isChecked());
    }

    private void loginWithPassword() {
        String clearPassword = password.getText().toString();
        if (clearPassword.isEmpty()) {
            password.setError("请输入密码");
            password.requestFocus();
            return;
        }
        ConnectionProfile profile = profileFromForm(savePassword.isChecked() ? clearPassword : "");
        if (profile == null) return;
        authenticate(profile, clearPassword, "正在登录 fnOS…", false);
    }

    private void resumeProfile(ConnectionProfile profile) {
        if (busy) return;
        fillForm(profile);
        if (profile.token.isEmpty() && profile.longToken.isEmpty() && !profile.password.isEmpty()) {
            authenticate(profile, profile.password, "正在登录 “" + profile.name + "”…", false);
            return;
        }
        authenticate(profile, null, "正在恢复 “" + profile.name + "” 的登录…", true);
    }

    private void authenticate(ConnectionProfile profile, @Nullable String clearPassword, String status, boolean resume) {
        setBusy(true, status);
        hideKeyboard();
        authClient.authenticate(profile, clearPassword, new FnOsAuthClient.Callback() {
            @Override
            public void onSuccess(ConnectionProfile authenticatedProfile) {
                setBusy(false, "");
                store.upsert(authenticatedProfile, true);
                renderHistoryButton();
                Intent intent = new Intent(LoginActivity.this, MainActivity.class);
                intent.putExtra(MainActivity.EXTRA_PROFILE_ID, authenticatedProfile.id);
                startActivity(intent);
                finish();
            }

            @Override
            public void onError(String message) {
                if (resume && !profile.password.isEmpty()) {
                    authenticate(profile, profile.password, "令牌已失效，正在使用已保存密码重新登录…", false);
                    return;
                }
                setBusy(false, "");
                fillForm(profile);
                password.requestFocus();
                Toast.makeText(LoginActivity.this, message, Toast.LENGTH_LONG).show();
                showKeyboard(password);
            }
        });
    }

    @Nullable
    private ConnectionProfile profileFromForm(String passwordToSave) {
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
                usernameValue,
                passwordToSave
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
        password.setText(profile.password);
        savePassword.setChecked(true);
    }

    private void renderHistoryButton() {
        if (historyButton == null || store == null) return;
        int count = store.list().size();
        historyButton.setVisibility(View.VISIBLE);
        historyButton.setText(count == 0 ? "历史连接" : "历史连接  ·  " + count);
    }

    private void configureSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        getWindow().setStatusBarColor(0xff071326);
        getWindow().setNavigationBarColor(0xff071326);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            int flags = getWindow().getDecorView().getSystemUiVisibility();
            flags &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) flags &= ~View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            getWindow().getDecorView().setSystemUiVisibility(flags);
        }
    }

    private void setBusy(boolean value, String status) {
        busy = value;
        loginButton.setEnabled(!value);
        historyButton.setEnabled(!value);
        progressRow.setVisibility(value ? View.VISIBLE : View.GONE);
        loginStatus.setText(status);
        profileName.setEnabled(!value);
        host.setEnabled(!value);
        port.setEnabled(!value);
        useHttps.setEnabled(!value);
        trustSelfSigned.setEnabled(!value && useHttps.isChecked());
        username.setEnabled(!value);
        password.setEnabled(!value);
        savePassword.setEnabled(!value);
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

    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_HISTORY || data == null) return;
        String profileId = data.getStringExtra(ConnectionHistoryActivity.EXTRA_PROFILE_ID);
        ConnectionProfile selected = store.find(profileId);
        if (selected == null) return;
        fillForm(selected);
        if (resultCode == RESULT_OK) {
            resumeProfile(selected);
        } else if (resultCode == ConnectionHistoryActivity.RESULT_EDIT_PROFILE) {
            host.requestFocus();
            showKeyboard(host);
        }
    }
}
