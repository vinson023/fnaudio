package com.fnaudio.client.ui;

import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.FnOsAuthClient;
import com.fnaudio.client.network.FnConnectResolver;

public final class LoginActivity extends AppCompatActivity {
    public static final String EXTRA_SKIP_AUTO_RESUME = "skip_auto_resume";
    public static final String EXTRA_PREFILL_ACTIVE_PROFILE = "prefill_active_profile";
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
    private ImageButton historyButton;
    private EditText fnId;
    private ImageButton fnConnectButton;
    private View progressRow;
    private TextView loginStatus;

    private SecureProfileStore store;
    private final FnOsAuthClient authClient = new FnOsAuthClient();
    private FnConnectResolver fnConnectResolver;
    private String editingProfileId = "";
    private boolean editingExistingProfile;
    private boolean busy;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureSystemBars();
        setContentView(R.layout.activity_login);
        WindowInsetsHelper.applySafePadding(findViewById(R.id.loginRoot));
        store = new SecureProfileStore(this);
        fnConnectResolver = new FnConnectResolver();
        bindViews();
        renderHistoryButton();

        boolean skipAutoResume = getIntent().getBooleanExtra(EXTRA_SKIP_AUTO_RESUME, false);
        boolean prefillActive = getIntent().getBooleanExtra(EXTRA_PREFILL_ACTIVE_PROFILE, false);
        ConnectionProfile active = store.active();
        // Do not flash or prefill the active FN Connect ID while an existing
        // session is being resumed. A deliberate return to Login uses a blank
        // form; a failed resume fills the saved profile in onError below.
        if (prefillActive && active != null) fillForm(active, false);
        else if (skipAutoResume || active == null) clearFormForNewProfile();
        if (!skipAutoResume && savedInstanceState == null && active != null && (!active.token.isEmpty() || !active.longToken.isEmpty())) {
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
        fnId = findViewById(R.id.fnId);
        fnConnectButton = findViewById(R.id.fnConnectButton);
        progressRow = findViewById(R.id.loginProgressRow);
        loginStatus = findViewById(R.id.loginStatus);

        if (port.getText().toString().trim().isEmpty()) port.setText("5666");
        loginButton.setOnClickListener(view -> loginWithPassword());
        historyButton.setOnClickListener(view -> startActivityForResult(
                new Intent(this, ConnectionHistoryActivity.class), REQUEST_HISTORY));
        fnConnectButton.setOnClickListener(view -> openFnConnect());
        useHttps.setOnCheckedChangeListener((button, checked) -> {
            trustSelfSigned.setEnabled(checked);
            String currentPort = port.getText().toString().trim();
            if (currentPort.isEmpty() || (!checked && "5667".equals(currentPort)) || (checked && "5666".equals(currentPort))) {
                port.setText(checked ? "5667" : "5666");
            }
        });
        trustSelfSigned.setEnabled(useHttps.isChecked());
    }

    private void openFnConnect() {
        String value = fnId.getText().toString().trim();
        if (value.isEmpty()) { fnId.setError("请输入 FN ID"); fnId.requestFocus(); return; }
        value = value.replaceFirst("(?i)^https?://", "").replaceFirst("/.*$", "");
        if (value.endsWith(".fnos.net")) value = value.substring(0, value.length() - ".fnos.net".length());
        setBusy(true, "正在通过 FN Connect 查找设备...");
        final String fnIdValue = value;
        final String passwordValue = password.getText().toString();
        fnConnectResolver.resolve(value, new FnConnectResolver.Callback() {
            @Override public void onResolved(ConnectionProfile resolved) {
                setBusy(false, "");
                fnId.setText(fnIdValue);
                host.setText(resolved.host);
                port.setText(String.valueOf(resolved.port));
                useHttps.setChecked(resolved.https);
                String user = username.getText().toString().trim();
                if (user.isEmpty() || passwordValue.isEmpty()) {
                    (user.isEmpty() ? username : password).requestFocus();
                    Toast.makeText(LoginActivity.this, "已找到设备，请输入账号和密码", Toast.LENGTH_SHORT).show();
                    return;
                }
                ConnectionProfile profile = ConnectionProfile.create(
                        "fnconnect:" + fnIdValue + ":" + user.toLowerCase(java.util.Locale.ROOT),
                        "FN Connect - " + fnIdValue, resolved.host, resolved.port, resolved.https,
                        false, user, savePassword.isChecked() ? passwordValue : "");
                authenticate(profile, passwordValue, "正在登录 FN Connect 设备...", false);
            }
            @Override public void onError(String message) {
                setBusy(false, "");
                Toast.makeText(LoginActivity.this, message, Toast.LENGTH_LONG).show();
            }
        });
    }

    private void loginWithPassword() {
        String address = fnId.getText().toString().trim().toLowerCase(java.util.Locale.ROOT);
        // A bare FN ID follows the official FN Connect resolver. Explicit IPs,
        // host names and URLs retain the direct fnOS login path.
        if (!address.isEmpty() && !address.contains(".") && !address.contains(":") && !address.contains("/")) {
            openFnConnect();
            return;
        }
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
        fillForm(profile, false);
        if (profile.token.isEmpty() && profile.longToken.isEmpty() && !profile.password.isEmpty()) {
            authenticate(profile, profile.password, "正在登录 “" + profile.name + "”…", false);
            return;
        }
        authenticate(profile, null, "正在恢复 “" + profile.name + "” 的登录…", true);
    }

    private void authenticate(ConnectionProfile profile, @Nullable String clearPassword, String status, boolean resume) {
        boolean preserveExplicitEdit = editingExistingProfile && store.find(profile.id) != null;
        setBusy(true, status);
        hideKeyboard();
        authClient.authenticate(this, profile, clearPassword, new FnOsAuthClient.Callback() {
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
                fillForm(profile, preserveExplicitEdit);
                password.requestFocus();
                Toast.makeText(LoginActivity.this, message, Toast.LENGTH_LONG).show();
                showKeyboard(password);
            }
        });
    }

    @Nullable
    private ConnectionProfile profileFromForm(String passwordToSave) {
        // The official-style primary field accepts either a local address or
        // an FN ID. A normal Login uses it as the direct fnOS address; the
        // adjacent history/Connect action explicitly starts FN Connect.
        String addressValue = fnId.getText().toString().trim();
        if (addressValue.isEmpty()) addressValue = host.getText().toString().trim();
        AddressParts address = parseAddress(addressValue);
        if (address.host.isEmpty()) {
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
        int portValue = address.port;
        try {
            if (portValue <= 0) portValue = useHttps.isChecked() ? 5667 : 5666;
            if (portValue < 1 || portValue > 65535) throw new NumberFormatException();
        } catch (NumberFormatException exception) {
            port.setError("端口号必须在 1–65535 之间");
            port.requestFocus();
            return null;
        }
        ConnectionProfile selected = store.find(editingProfileId);
        boolean sameAsSelected = selected != null && selected.matchesConnection(
                address.host, portValue, useHttps.isChecked(), usernameValue);
        String requestedName = profileName.getText().toString().trim();
        if (!sameAsSelected || requestedName.startsWith("FN Connect - ")) requestedName = address.host;
        ConnectionProfile result = ConnectionProfile.create(
                profileIdForForm(address.host, portValue, useHttps.isChecked(), usernameValue),
                requestedName.isEmpty() ? address.host : requestedName,
                address.host,
                portValue,
                useHttps.isChecked(),
                trustSelfSigned.isChecked(),
                usernameValue,
                passwordToSave
        );
        ConnectionProfile existing = store.find(result.id);
        if (result.trustSelfSigned && existing != null && existing.matchesConnection(
                result.host, result.port, result.https, result.username)) {
            result = result.withCertificatePin(existing.certificatePinSha256);
        }
        return result;
    }

    private AddressParts parseAddress(String raw) {
        String value = raw == null ? "" : raw.trim().replaceFirst("(?i)^https?://", "");
        int slash = value.indexOf('/');
        if (slash >= 0) value = value.substring(0, slash);
        if (value.startsWith("[") && value.contains("]")) {
            int close = value.indexOf(']');
            String hostValue = value.substring(1, close);
            String tail = value.substring(close + 1);
            return new AddressParts(hostValue, tail.startsWith(":") && tail.substring(1).matches("\\d+") ? Integer.parseInt(tail.substring(1)) : 0);
        }
        int colon = value.lastIndexOf(':');
        if (colon > 0 && value.indexOf(':') == colon && value.substring(colon + 1).matches("\\d+")) {
            return new AddressParts(value.substring(0, colon), Integer.parseInt(value.substring(colon + 1)));
        }
        return new AddressParts(value, 0);
    }

    private static final class AddressParts {
        final String host;
        final int port;
        AddressParts(String host, int port) { this.host = host == null ? "" : host.trim(); this.port = port; }
    }

    private String profileIdForForm(String hostValue, int portValue, boolean httpsValue, String usernameValue) {
        ConnectionProfile selected = store.find(editingProfileId);
        if (selected != null && (editingExistingProfile
                || selected.matchesConnection(hostValue, portValue, httpsValue, usernameValue))) {
            return selected.id;
        }
        for (ConnectionProfile profile : store.list()) {
            if (profile.matchesConnection(hostValue, portValue, httpsValue, usernameValue)) return profile.id;
        }
        return "";
    }

    private void fillForm(ConnectionProfile profile, boolean explicitEdit) {
        editingProfileId = profile.id;
        editingExistingProfile = explicitEdit;
        profileName.setText(profile.name);
        host.setText(profile.host);
        // FN Connect keeps the resolved public/relay endpoint private to the
        // connection profile. The login field should always show the FN ID.
        fnId.setText(displayAddress(profile));
        port.setText(String.valueOf(profile.port));
        useHttps.setChecked(profile.https);
        trustSelfSigned.setChecked(profile.trustSelfSigned);
        trustSelfSigned.setEnabled(profile.https);
        username.setText(profile.username);
        password.setText(profile.password);
        savePassword.setChecked(true);
    }

    private void clearFormForNewProfile() {
        editingProfileId = "";
        editingExistingProfile = false;
        profileName.setText("");
        host.setText("");
        fnId.setText("");
        useHttps.setChecked(false);
        trustSelfSigned.setChecked(false);
        trustSelfSigned.setEnabled(false);
        port.setText("5666");
        username.setText("");
        password.setText("");
        savePassword.setChecked(true);
        loginStatus.setText("");
        host.requestFocus();
        showKeyboard(host);
    }

    private String fnConnectId(ConnectionProfile profile) {
        String prefix = "FN Connect - ";
        if (profile != null && profile.name != null && profile.name.startsWith(prefix)) {
            String value = profile.name.substring(prefix.length()).trim();
            if (!value.isEmpty()) return value;
        }
        return profile == null ? "" : profile.host;
    }

    private String displayAddress(ConnectionProfile profile) {
        if (profile == null) return "";
        if (profile.name != null && profile.name.startsWith("FN Connect - ")) return fnConnectId(profile);
        int defaultPort = profile.https ? 5667 : 5666;
        if (profile.port <= 0 || profile.port == defaultPort) return profile.host;
        String hostValue = profile.host.contains(":") ? "[" + profile.host + "]" : profile.host;
        return hostValue + ":" + profile.port;
    }

    private void renderHistoryButton() {
        if (historyButton == null || store == null) return;
        int count = store.list().size();
        historyButton.setVisibility(View.VISIBLE);
        historyButton.setContentDescription(count == 0 ? "历史连接" : "历史连接，" + count + " 个记录");
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
        fnId.setEnabled(!value);
        fnConnectButton.setEnabled(!value);
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
        if (requestCode != REQUEST_HISTORY) return;
        if (resultCode == ConnectionHistoryActivity.RESULT_NEW_PROFILE) {
            clearFormForNewProfile();
            return;
        }
        if (data == null) return;
        String profileId = data.getStringExtra(ConnectionHistoryActivity.EXTRA_PROFILE_ID);
        ConnectionProfile selected = store.find(profileId);
        if (selected == null) return;
        if (resultCode == RESULT_OK) {
            resumeProfile(selected);
        } else if (resultCode == ConnectionHistoryActivity.RESULT_EDIT_PROFILE) {
            fillForm(selected, true);
            host.requestFocus();
            showKeyboard(host);
        }
    }
}
