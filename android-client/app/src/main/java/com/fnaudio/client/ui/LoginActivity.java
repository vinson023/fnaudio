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
import android.text.method.HideReturnsTransformationMethod;
import android.text.method.PasswordTransformationMethod;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.FnOsAuthClient;
import com.fnaudio.client.network.FnConnectResolver;
import com.fnaudio.client.network.FnConnectSettings;

public final class LoginActivity extends AppCompatActivity {
    public static final String EXTRA_SKIP_AUTO_RESUME = "skip_auto_resume";
    public static final String EXTRA_PREFILL_ACTIVE_PROFILE = "prefill_active_profile";
    private static final int REQUEST_HISTORY = 701;
    private static final int REQUEST_FN_CONNECT_SETTINGS = 702;

    private EditText profileName;
    private EditText host;
    private EditText port;
    private CheckBox useHttps;
    private CheckBox trustSelfSigned;
    private EditText username;
    private EditText password;
    private EditText accessCode;
    private ImageButton passwordVisibilityButton;
    private ImageButton accessCodeVisibilityButton;
    private CheckBox savePassword;
    private Button loginButton;
    private ImageButton historyButton;
    private EditText fnId;
    private ImageButton fnConnectButton;
    private ImageButton fnConnectSettingsButton;
    private TextView fnConnectSettingsSummary;
    private View progressRow;
    private TextView loginStatus;

    private SecureProfileStore store;
    private final FnOsAuthClient authClient = new FnOsAuthClient();
    private FnConnectResolver fnConnectResolver;
    private String editingProfileId = "";
    private boolean editingExistingProfile;
    private boolean busy;
    private boolean destroyed;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        destroyed = false;
        configureSystemBars();
        setContentView(R.layout.activity_login);
        WindowInsetsHelper.applySafePadding(findViewById(R.id.loginRoot));
        store = new SecureProfileStore(this);
        fnConnectResolver = new FnConnectResolver(this);
        bindViews();
        renderHistoryButton();

        boolean skipAutoResume = safeBooleanExtra(getIntent(), EXTRA_SKIP_AUTO_RESUME, false);
        boolean prefillActive = safeBooleanExtra(getIntent(), EXTRA_PREFILL_ACTIVE_PROFILE, false);
        ConnectionProfile active = store.active();
        // Do not flash or prefill the active FN Connect ID while an existing
        // session is being resumed. A deliberate return to Login uses a blank
        // form; a failed resume fills the saved profile in onError below.
        if (prefillActive && active != null) fillForm(active, false);
        else if (skipAutoResume || active == null) clearFormForNewProfile();
        if (!skipAutoResume && savedInstanceState == null && active != null && (!active.token.isEmpty() || !active.longToken.isEmpty())) {
            loginStatus.postDelayed(() -> {
                if (!destroyed) resumeProfile(active);
            }, 220);
        }
    }

    private static boolean safeBooleanExtra(@Nullable Intent intent, String key, boolean fallback) {
        if (intent == null || key == null) return fallback;
        try {
            return intent.getBooleanExtra(key, fallback);
        } catch (RuntimeException ignored) {
            return fallback;
        }
    }

    private static String safeStringExtra(@Nullable Intent intent, String key) {
        if (intent == null || key == null) return "";
        try {
            String value = intent.getStringExtra(key);
            return value == null ? "" : value;
        } catch (RuntimeException ignored) {
            return "";
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderHistoryButton();
        renderFnConnectSettingsSummary();
    }

    @Override
    protected void onDestroy() {
        destroyed = true;
        authClient.cancel();
        if (fnConnectResolver != null) fnConnectResolver.close();
        super.onDestroy();
    }

    private void bindViews() {
        profileName = findViewById(R.id.profileName);
        host = findViewById(R.id.host);
        port = findViewById(R.id.port);
        useHttps = findViewById(R.id.useHttps);
        trustSelfSigned = findViewById(R.id.trustSelfSigned);
        username = findViewById(R.id.username);
        password = findViewById(R.id.password);
        accessCode = findViewById(R.id.accessCode);
        passwordVisibilityButton = findViewById(R.id.passwordVisibilityButton);
        accessCodeVisibilityButton = findViewById(R.id.accessCodeVisibilityButton);
        savePassword = findViewById(R.id.savePassword);
        loginButton = findViewById(R.id.loginButton);
        historyButton = findViewById(R.id.historyButton);
        fnId = findViewById(R.id.fnId);
        fnConnectButton = findViewById(R.id.fnConnectButton);
        fnConnectSettingsButton = findViewById(R.id.fnConnectSettingsButton);
        fnConnectSettingsSummary = findViewById(R.id.fnConnectSettingsSummary);
        progressRow = findViewById(R.id.loginProgressRow);
        loginStatus = findViewById(R.id.loginStatus);

        if (port.getText().toString().trim().isEmpty()) port.setText("5666");
        loginButton.setOnClickListener(view -> loginWithPassword());
        passwordVisibilityButton.setOnClickListener(view -> toggleSecretVisibility(password, passwordVisibilityButton, "密码"));
        accessCodeVisibilityButton.setOnClickListener(view -> toggleSecretVisibility(accessCode, accessCodeVisibilityButton, "访问码"));
        historyButton.setOnClickListener(view -> startActivityForResult(
                new Intent(this, ConnectionHistoryActivity.class), REQUEST_HISTORY));
        fnConnectButton.setOnClickListener(view -> openFnConnect());
        fnConnectSettingsButton.setOnClickListener(view -> startActivityForResult(
                new Intent(this, FnConnectSettingsActivity.class), REQUEST_FN_CONNECT_SETTINGS));
        useHttps.setOnCheckedChangeListener((button, checked) -> {
            trustSelfSigned.setEnabled(checked);
            String currentPort = port.getText().toString().trim();
            if (currentPort.isEmpty() || (!checked && "5667".equals(currentPort)) || (checked && "5666".equals(currentPort))) {
                port.setText(checked ? "5667" : "5666");
            }
        });
        trustSelfSigned.setEnabled(useHttps.isChecked());
        renderFnConnectSettingsSummary();
    }

    private static void toggleSecretVisibility(EditText field, ImageButton button, String label) {
        boolean visible = field.getTransformationMethod() == null;
        int selection = field.getSelectionStart();
        field.setTransformationMethod(visible ? PasswordTransformationMethod.getInstance() : HideReturnsTransformationMethod.getInstance());
        field.setSelection(Math.max(0, Math.min(selection, field.length())));
        button.setImageResource(visible ? R.drawable.ic_visibility_off : R.drawable.ic_visibility);
        button.setContentDescription(visible ? "显示" + label : "隐藏" + label);
    }

    private void openFnConnect() {
        String value = fnId.getText().toString().trim();
        if (value.isEmpty()) { fnId.setError("请输入 FN ID"); fnId.requestFocus(); return; }
        value = value.replaceFirst("(?i)^https?://", "").replaceFirst("/.*$", "");
        if (value.endsWith(".fnos.net")) value = value.substring(0, value.length() - ".fnos.net".length());
        setBusy(true, "正在通过 FN Connect 查找设备...");
        final String fnIdValue = value;
        final String passwordValue = password.getText().toString();
        FnConnectSettings settings = new FnConnectSettings(this);
        String effectiveMode = settings.effectiveMode();
        FnConnectResolver.Mode connectMode = FnConnectSettings.resolverMode(effectiveMode);
        fnConnectResolver.resolve(value, connectMode, new FnConnectResolver.Callback() {
            @Override public void onResolved(ConnectionProfile resolved) {
                if (destroyed) return;
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
                        false, user, savePassword.isChecked() ? passwordValue : "")
                        .withFnConnectMode(effectiveMode)
                        .withAccessCode(accessCode.getText().toString());
                authenticate(profile, passwordValue, "正在登录 FN Connect 设备...", false);
            }
            @Override public void onError(String message) {
                if (destroyed) return;
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
        String connectId = fnConnectId(profile);
        if ((profile.id.startsWith("fnconnect:") || profile.name.startsWith("FN Connect - "))
                && !connectId.isEmpty()) {
            setBusy(true, fnConnectStatus(profile.fnConnectMode));
            FnConnectResolver.Mode connectMode = FnConnectSettings.resolverMode(profile.fnConnectMode);
            fnConnectResolver.resolve(connectId, connectMode, new FnConnectResolver.Callback() {
                @Override public void onResolved(ConnectionProfile route) {
                    if (destroyed) return;
                    ConnectionProfile refreshed = profile.withEndpoint(route.host, route.port, route.https);
                    store.upsert(refreshed, true);
                    resumeResolvedProfile(refreshed);
                }

                @Override public void onError(String message) {
                    if (destroyed) return;
                    if (FnConnectSettings.MODE_RELAY.equals(profile.fnConnectMode)) {
                        setBusy(false, "");
                        fillForm(profile, false);
                        Toast.makeText(LoginActivity.this, message, Toast.LENGTH_LONG).show();
                        return;
                    }
                    // Endpoint discovery is advisory during resume. The last
                    // official endpoint may still work when fnos.net is briefly unavailable.
                    resumeResolvedProfile(profile);
                }
            });
            return;
        }
        resumeResolvedProfile(profile);
    }

    private void resumeResolvedProfile(ConnectionProfile profile) {
        if (profile.token.isEmpty() && profile.longToken.isEmpty() && !profile.password.isEmpty()) {
            authenticate(profile, profile.password, "正在登录 “" + profile.name + "”…", false);
            return;
        }
        authenticate(profile, null, "正在恢复 “" + profile.name + "” 的登录…", true);
    }

    private void authenticate(ConnectionProfile profile, @Nullable String clearPassword, String status, boolean resume) {
        authenticate(profile, clearPassword, status, resume, resume);
    }

    private void authenticate(ConnectionProfile profile, @Nullable String clearPassword, String status,
                              boolean allowPasswordFallback, boolean storedRecovery) {
        boolean preserveExplicitEdit = editingExistingProfile && store.find(profile.id) != null;
        setBusy(true, status);
        hideKeyboard();
        authClient.authenticate(this, profile, clearPassword, new FnOsAuthClient.Callback() {
            @Override
            public void onSuccess(ConnectionProfile authenticatedProfile) {
                if (destroyed) return;
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
                if (destroyed) return;
                setBusy(false, "");
                fillForm(profile, preserveExplicitEdit);
                Toast.makeText(LoginActivity.this, message, Toast.LENGTH_LONG).show();
            }

            @Override
            public void onCredentialRejected(String message) {
                if (destroyed) return;
                if (allowPasswordFallback && !profile.password.isEmpty()) {
                    authenticate(profile, profile.password, "令牌已失效，正在使用已保存密码重新登录…", false, true);
                    return;
                }
                setBusy(false, "");
                ConnectionProfile editableProfile = profile;
                if (storedRecovery) {
                    editableProfile = profile.withTokens("", "");
                    store.upsert(editableProfile, true);
                }
                fillForm(editableProfile, preserveExplicitEdit);
                password.requestFocus();
                Toast.makeText(LoginActivity.this,
                        storedRecovery ? "登录令牌已失效，请重新输入密码。" : message,
                        Toast.LENGTH_LONG).show();
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
        boolean httpsValue = address.https != null ? address.https : useHttps.isChecked();
        if (address.https != null && useHttps.isChecked() != httpsValue) {
            useHttps.setChecked(httpsValue);
        }
        int portValue = address.port;
        try {
            if (portValue < 0) throw new NumberFormatException();
            if (portValue <= 0) portValue = httpsValue ? 5667 : 5666;
            if (portValue < 1 || portValue > 65535) throw new NumberFormatException();
        } catch (NumberFormatException exception) {
            port.setError("端口号必须在 1–65535 之间");
            port.requestFocus();
            return null;
        }
        ConnectionProfile selected = store.find(editingProfileId);
        boolean sameAsSelected = selected != null && selected.matchesConnection(
                address.host, portValue, httpsValue, usernameValue);
        String requestedName = profileName.getText().toString().trim();
        if (!sameAsSelected || requestedName.startsWith("FN Connect - ")) requestedName = address.host;
        ConnectionProfile result = ConnectionProfile.create(
                profileIdForForm(address.host, portValue, httpsValue, usernameValue),
                requestedName.isEmpty() ? address.host : requestedName,
                address.host,
                portValue,
                httpsValue,
                trustSelfSigned.isChecked(),
                usernameValue,
                passwordToSave
        ).withAccessCode(accessCode.getText().toString());
        ConnectionProfile existing = store.find(result.id);
        if (result.trustSelfSigned && existing != null && existing.matchesConnection(
                result.host, result.port, result.https, result.username)) {
            result = result.withCertificatePin(existing.certificatePinSha256);
        }
        return result;
    }

    private AddressParts parseAddress(String raw) {
        String value = raw == null ? "" : raw.trim();
        Boolean explicitHttps = null;
        if (value.regionMatches(true, 0, "https://", 0, 8)) {
            explicitHttps = true;
            value = value.substring(8);
        } else if (value.regionMatches(true, 0, "http://", 0, 7)) {
            explicitHttps = false;
            value = value.substring(7);
        }
        int end = value.length();
        for (char delimiter : new char[]{'/', '?', '#'}) {
            int index = value.indexOf(delimiter);
            if (index >= 0 && index < end) end = index;
        }
        value = value.substring(0, end);
        // Userinfo is not a supported login field and must never become part
        // of the host used for authentication or origin checks.
        if (value.indexOf('@') >= 0) return new AddressParts("", -1, explicitHttps);
        if (value.startsWith("[") && value.contains("]")) {
            int close = value.indexOf(']');
            String hostValue = value.substring(1, close);
            String tail = value.substring(close + 1);
            return new AddressParts(hostValue, tail.startsWith(":") ? parsePort(tail.substring(1)) : 0, explicitHttps);
        }
        int colon = value.lastIndexOf(':');
        if (colon > 0 && value.indexOf(':') == colon) {
            return new AddressParts(value.substring(0, colon), parsePort(value.substring(colon + 1)), explicitHttps);
        }
        return new AddressParts(value, 0, explicitHttps);
    }

    private static int parsePort(String raw) {
        if (raw == null || !raw.matches("\\d+")) return -1;
        try {
            int parsed = Integer.parseInt(raw);
            return parsed >= 1 && parsed <= 65535 ? parsed : -1;
        } catch (NumberFormatException exception) {
            return -1;
        }
    }

    private static final class AddressParts {
        final String host;
        final int port;
        final Boolean https;
        AddressParts(String host, int port, Boolean https) {
            this.host = host == null ? "" : host.trim();
            this.port = port;
            this.https = https;
        }
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
        accessCode.setText(profile.accessCode);
        savePassword.setChecked(true);
        renderFnConnectSettingsSummary();
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
        accessCode.setText("");
        savePassword.setChecked(true);
        renderFnConnectSettingsSummary();
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

    private void renderFnConnectSettingsSummary() {
        if (fnConnectSettingsSummary == null) return;
        FnConnectSettings settings = new FnConnectSettings(this);
        String mode = settings.mode();
        String p2p = settings.isP2pEnabled() ? "P2P 已开启" : "P2P 已关闭";
        fnConnectSettingsSummary.setText("FN Connect：" + FnConnectSettings.label(mode) + " · " + p2p);
    }

    private static String fnConnectStatus(String mode) {
        if (FnConnectSettings.MODE_RELAY.equals(mode)) return "正在建立 FN Connect P2P 中继...";
        if (FnConnectSettings.MODE_SPEED.equals(mode)) return "正在选择最快的 FN Connect 链路...";
        return "正在刷新 FN Connect 公网地址...";
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
        fnConnectSettingsButton.setEnabled(!value);
    }

    private void hideKeyboard() {
        View view = getCurrentFocus();
        if (view == null) return;
        InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
        manager.hideSoftInputFromWindow(view.getWindowToken(), 0);
    }

    private void showKeyboard(View view) {
        view.postDelayed(() -> {
            if (destroyed || isFinishing()) return;
            InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            manager.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT);
        }, 180);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_FN_CONNECT_SETTINGS) {
            renderFnConnectSettingsSummary();
            return;
        }
        if (requestCode != REQUEST_HISTORY) return;
        if (resultCode == ConnectionHistoryActivity.RESULT_NEW_PROFILE) {
            clearFormForNewProfile();
            return;
        }
        if (data == null) return;
        String profileId = safeStringExtra(data, ConnectionHistoryActivity.EXTRA_PROFILE_ID);
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
