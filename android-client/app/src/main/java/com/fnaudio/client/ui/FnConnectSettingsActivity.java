package com.fnaudio.client.ui;

import android.os.Bundle;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.SwitchCompat;
import androidx.core.view.WindowCompat;

import com.fnaudio.client.R;
import com.fnaudio.client.network.FnConnectSettings;

/** FN Connect route preferences shown from the login-page settings button. */
public final class FnConnectSettingsActivity extends AppCompatActivity {
    private FnConnectSettings settings;
    private RadioGroup routeMode;
    private RadioButton speedMode;
    private RadioButton publicMode;
    private RadioButton relayMode;
    private SwitchCompat p2pEnabled;
    private TextView hint;
    private boolean binding;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        configureSystemBars();
        setContentView(R.layout.activity_fn_connect_settings);
        WindowInsetsHelper.applySafePadding(findViewById(R.id.fnConnectSettingsRoot));
        settings = new FnConnectSettings(this);
        routeMode = findViewById(R.id.fnConnectRouteMode);
        speedMode = findViewById(R.id.fnConnectSpeedMode);
        publicMode = findViewById(R.id.fnConnectPublicMode);
        relayMode = findViewById(R.id.fnConnectRelayMode);
        p2pEnabled = findViewById(R.id.fnConnectP2pEnabled);
        hint = findViewById(R.id.fnConnectSettingsHint);
        findViewById(R.id.fnConnectSettingsBackButton).setOnClickListener(view -> finish());

        routeMode.setOnCheckedChangeListener((group, checkedId) -> save());
        p2pEnabled.setOnCheckedChangeListener((button, checked) -> save());
        bindSavedState();
    }

    private void bindSavedState() {
        binding = true;
        String mode = settings.mode();
        if (FnConnectSettings.MODE_RELAY.equals(mode)) relayMode.setChecked(true);
        else if (FnConnectSettings.MODE_PUBLIC.equals(mode)) publicMode.setChecked(true);
        else speedMode.setChecked(true);
        p2pEnabled.setChecked(settings.isP2pEnabled());
        binding = false;
        renderState();
    }

    private void save() {
        if (binding) return;
        if (!p2pEnabled.isChecked() && !FnConnectSettings.MODE_PUBLIC.equals(selectedMode())) {
            binding = true;
            publicMode.setChecked(true);
            binding = false;
        }
        settings.save(selectedMode(), p2pEnabled.isChecked());
        renderState();
    }

    private String selectedMode() {
        int checked = routeMode.getCheckedRadioButtonId();
        if (checked == R.id.fnConnectRelayMode) return FnConnectSettings.MODE_RELAY;
        if (checked == R.id.fnConnectPublicMode) return FnConnectSettings.MODE_PUBLIC;
        return FnConnectSettings.MODE_SPEED;
    }

    private void renderState() {
        boolean p2p = p2pEnabled.isChecked();
        speedMode.setEnabled(p2p);
        relayMode.setEnabled(p2p);
        if (!p2p) hint.setText("P2P 已关闭，FN Connect 将始终使用公网连接");
        else if (FnConnectSettings.MODE_SPEED.equals(selectedMode())) hint.setText("优先使用最快可用链路，公网不可用时自动尝试 P2P 中继");
        else if (FnConnectSettings.MODE_RELAY.equals(selectedMode())) hint.setText("强制通过 P2P 中继连接，不回退到公网");
        else hint.setText("仅使用 FN Connect 发布的公网 IPv6 或 IPv4 地址");
    }

    private void configureSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        getWindow().setStatusBarColor(0xff071326);
        getWindow().setNavigationBarColor(0xff071326);
    }
}
