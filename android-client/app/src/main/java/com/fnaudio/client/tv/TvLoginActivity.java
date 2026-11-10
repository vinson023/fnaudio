package com.fnaudio.client.tv;

import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.FnOsAuthClient;

import java.util.List;
import java.util.Locale;

/**
 * Television entry point.
 *
 * <p>A remote is a poor text input device, so the first path offered is the one
 * that types nothing: the page shows a six-digit code and a QR that carries the
 * television's own address, the phone scans it, and the connection arrives over
 * the LAN. Stored profiles are the second path, and a four-field form the third.
 *
 * <p>The QR and the digits are the same thing: a phone that cannot scan - no
 * camera, no permission, a different subnet - can still type six digits. Both
 * feed the same {@link TvPairingServer} request.
 */
public final class TvLoginActivity extends AppCompatActivity {
    private final FnOsAuthClient authClient = new FnOsAuthClient();

    private SecureProfileStore store;
    private TvPairingCard pairingCard;
    private LinearLayout profileList;
    private LinearLayout form;
    private TextView status;

    private EditText hostField;
    private EditText portField;
    private EditText userField;
    private EditText passwordField;

    @Nullable private TvPairingServer pairingServer;
    /** The view the page wants focused once it is on screen. */
    @Nullable private View initialFocus;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        store = new SecureProfileStore(this);
        setContentView(buildUi());
        TvUi.hideSystemBars(this);
        renderProfiles();
        startPairing();
    }

    // ------------------------------------------------------------------ 布局

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.HORIZONTAL);
        root.setBackgroundColor(TvTheme.BG);
        root.setPadding(TvTheme.dp(this, 48), TvTheme.dp(this, 26),
                TvTheme.dp(this, 40), TvTheme.dp(this, 20));

        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        root.addView(left, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 0.86f));

        TextView brand = new TextView(this);
        brand.setText("fnAudio");
        brand.setTextColor(TvTheme.TEXT);
        brand.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.HERO);
        brand.setTypeface(null, android.graphics.Typeface.BOLD);
        left.addView(brand);

        TextView tagline = new TextView(this);
        tagline.setText("连接到你的音乐库");
        tagline.setTextColor(TvTheme.TEXT_3);
        tagline.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        tagline.setPadding(0, TvTheme.dp(this, 2), 0, TvTheme.dp(this, 16));
        left.addView(tagline);

        pairingCard = new TvPairingCard(this);
        pairingCard.setOnRefresh(this::startPairing);
        LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(
                TvTheme.dp(this, 280), TvTheme.dp(this, 330));
        left.addView(pairingCard, cardParams);

        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setPadding(TvTheme.dp(this, 32), 0, 0, 0);
        root.addView(right, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1.14f));

        ScrollView scroll = new ScrollView(this);
        scroll.setVerticalScrollBarEnabled(false);
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(column);
        right.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        profileList = new LinearLayout(this);
        profileList.setOrientation(LinearLayout.VERTICAL);
        column.addView(profileList);

        form = buildForm();
        column.addView(form);

        status = new TextView(this);
        status.setTextColor(TvTheme.TEXT_2);
        status.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        status.setPadding(0, TvTheme.dp(this, 14), 0, 0);
        right.addView(status);

        return root;
    }

    private LinearLayout buildForm() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setVisibility(View.GONE);

        TextView heading = new TextView(this);
        heading.setText("手动新增连接");
        heading.setTextColor(TvTheme.TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        heading.setPadding(0, TvTheme.dp(this, 6), 0, TvTheme.dp(this, 10));
        box.addView(heading);

        hostField = input(box, "设备地址，例如 192.168.5.141", InputType.TYPE_CLASS_TEXT);
        portField = input(box, "端口（默认 5666）", InputType.TYPE_CLASS_NUMBER);
        userField = input(box, "用户名", InputType.TYPE_CLASS_TEXT);
        passwordField = input(box, "密码", InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        passwordField.setImeOptions(EditorInfo.IME_ACTION_DONE);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setPadding(0, TvTheme.dp(this, 10), 0, 0);
        box.addView(actions);

        TextView submit = pill("连接", true);
        submit.setOnClickListener(view -> submitManual());
        actions.addView(submit);

        TextView cancel = pill("取消", false);
        LinearLayout.LayoutParams cancelParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cancelParams.leftMargin = TvTheme.dp(this, 12);
        cancel.setOnClickListener(view -> {
            form.setVisibility(View.GONE);
            renderProfiles();
        });
        actions.addView(cancel, cancelParams);

        return box;
    }

    private EditText input(LinearLayout parent, String hint, int inputType) {
        EditText field = new EditText(this);
        field.setHint(hint);
        field.setHintTextColor(TvTheme.TEXT_4);
        field.setTextColor(TvTheme.TEXT);
        field.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        field.setInputType(inputType);
        field.setSingleLine(true);
        field.setBackground(TvTheme.rounded(this, TvTheme.CARD_FILL, 10f));
        field.setPadding(TvTheme.dp(this, 16), TvTheme.dp(this, 9),
                TvTheme.dp(this, 16), TvTheme.dp(this, 9));
        // The keyboard belongs to an explicit OK press: wiring it to focus means
        // the soft keyboard covers the form the moment the page opens.
        field.setShowSoftInputOnFocus(false);
        field.setOnKeyListener((view, keyCode, event) -> {
            if (event.getAction() == android.view.KeyEvent.ACTION_DOWN
                    && (keyCode == android.view.KeyEvent.KEYCODE_DPAD_CENTER
                    || keyCode == android.view.KeyEvent.KEYCODE_ENTER)) {
                showKeyboard(field);
                return true;
            }
            return false;
        });
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = TvTheme.dp(this, 8);
        parent.addView(field, params);
        return field;
    }

    private void showKeyboard(EditText field) {
        field.requestFocus();
        android.view.inputmethod.InputMethodManager keyboard =
                getSystemService(android.view.inputmethod.InputMethodManager.class);
        if (keyboard != null) keyboard.showSoftInput(field,
                android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT);
    }

    private TextView pill(String label, boolean primary) {
        TextView button = new TextView(this);
        button.setText(label);
        button.setTextColor(primary ? 0xFF071018 : TvTheme.TEXT);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        button.setTypeface(null, android.graphics.Typeface.BOLD);
        button.setGravity(Gravity.CENTER);
        button.setFocusable(true);
        button.setFocusableInTouchMode(false);
        button.setPadding(TvTheme.dp(this, 26), TvTheme.dp(this, 11),
                TvTheme.dp(this, 26), TvTheme.dp(this, 11));
        button.setBackground(TvTheme.rounded(this,
                primary ? TvTheme.ACCENT : TvTheme.CARD_FILL, TvTheme.R_PILL));
        button.setForeground(TvTheme.focusRing(this, TvTheme.R_PILL));
        TvUi.applyFocusScale(button, 1.06f);
        return button;
    }

    // ------------------------------------------------------------------ 配对

    /**
     * (Re)starts the temporary pairing server and paints a fresh code.
     *
     * <p>Called on open and again whenever the previous code expired or failed:
     * the code is single-use, so a retry has to mint a new one rather than reuse
     * the six digits already on screen.
     */
    private void startPairing() {
        stopPairing();
        TvPairingServer server = new TvPairingServer(new TvPairingServer.Listener() {
            @Override public void onPaired(ConnectionProfile profile) {
                pairingServer = null;
                pairingCard.showState("正在连接 " + profile.host + " …");
                status.setText("已收到手机发来的连接");
                authenticatePaired(profile);
            }

            @Override public void onClosed(String reason) {
                pairingServer = null;
                pairingCard.showState(reason + "\n按 OK 换一个码");
            }
        });
        if (!server.start()) {
            pairingCard.setUnavailable("这台电视没有可用的局域网地址\n请用右侧的方式连接");
            return;
        }
        pairingServer = server;
        String uri = PairingPayload.of(server.host(), server.port(), server.code()).toUri();
        pairingCard.setCode(uri, server.code());
    }

    private void stopPairing() {
        if (pairingServer == null) return;
        pairingServer.stop();
        pairingServer = null;
    }

    /** Signs in with the long token the phone handed over; no password involved. */
    private void authenticatePaired(ConnectionProfile profile) {
        authClient.authenticate(this, profile, null, new FnOsAuthClient.Callback() {
            @Override public void onSuccess(ConnectionProfile authenticatedProfile) {
                store.upsert(authenticatedProfile, true);
                openShell(authenticatedProfile);
            }

            @Override public void onError(String message) {
                pairingCard.showState("连不上 " + profile.host + "\n按 OK 重新生成配对码");
                status.setText(message == null || message.isEmpty() ? "连接失败" : message);
            }

            @Override public void onCredentialRejected(String message) {
                pairingCard.showState("手机上的登录已过期\n请在手机上重新登录后再发送");
                status.setText(message == null || message.isEmpty() ? "登录已失效" : message);
            }
        });
    }

    private void openShell(ConnectionProfile profile) {
        Intent intent = new Intent(this, TvShellActivity.class);
        intent.putExtra(TvShellActivity.EXTRA_PROFILE_ID, profile.id);
        startActivity(intent);
        finish();
    }

    // ------------------------------------------------------------------ 连接列表

    private void renderProfiles() {
        profileList.removeAllViews();
        List<ConnectionProfile> profiles = store.list();
        form.setVisibility(View.GONE);

        if (profiles.isEmpty()) {
            TextView empty = new TextView(this);
            empty.setText("还没有已保存的连接。\n用手机扫码最快，也可以手动填写。");
            empty.setTextColor(TvTheme.TEXT_2);
            empty.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
            empty.setLineSpacing(TvTheme.dp(this, 4), 1f);
            empty.setPadding(0, 0, 0, TvTheme.dp(this, 18));
            profileList.addView(empty);
            initialFocus = pairingCard;
            applyInitialFocus();
            return;
        }

        TextView heading = new TextView(this);
        heading.setText("选择已保存的连接");
        heading.setTextColor(TvTheme.TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, TvTheme.LIST_TITLE);
        heading.setPadding(0, 0, 0, TvTheme.dp(this, 10));
        profileList.addView(heading);

        View firstRow = null;
        for (ConnectionProfile profile : profiles) {
            View row = profileRow(profile);
            profileList.addView(row);
            if (firstRow == null) firstRow = row;
        }

        TextView addAnother = pill("新增连接", false);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.topMargin = TvTheme.dp(this, 18);
        addAnother.setOnClickListener(view -> openForm());
        profileList.addView(addAnother, params);

        // A television has no pointer to fall back on: with nothing focused the
        // first OK press only moves the highlight, so the most likely action is
        // focused up front.
        if (firstRow != null) {
            firstRow.setNextFocusUpId(pairingCard.getId());
            pairingCard.setNextFocusDownId(firstRow.getId());
        }
        initialFocus = firstRow;
        applyInitialFocus();
    }

    /**
     * The window assigns focus itself once attached, and picks the last
     * focusable in the tree, so a request made during inflation loses the race.
     */
    private void applyInitialFocus() {
        if (initialFocus == null) return;
        View target = initialFocus;
        target.post(() -> {
            if (!target.isFocused()) target.requestFocus();
        });
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus && initialFocus != null && !initialFocus.isFocused()) applyInitialFocus();
    }

    private View profileRow(ConnectionProfile profile) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setFocusable(true);
        row.setFocusableInTouchMode(false);
        row.setPadding(TvTheme.dp(this, 20), TvTheme.dp(this, 14),
                TvTheme.dp(this, 20), TvTheme.dp(this, 14));
        row.setBackground(TvTheme.cardBackground(this, 10f));
        row.setForeground(TvTheme.focusRing(this, 10f));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = TvTheme.dp(this, 8);
        row.setLayoutParams(params);

        LinearLayout labels = new LinearLayout(this);
        labels.setOrientation(LinearLayout.VERTICAL);
        row.addView(labels, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView name = new TextView(this);
        name.setText(profile.name == null || profile.name.isEmpty() ? profile.host : profile.name);
        name.setTextColor(TvTheme.TEXT);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f);
        name.setSingleLine(true);
        labels.addView(name);

        TextView detail = new TextView(this);
        detail.setText(profile.host + ":" + profile.port + " · " + profile.username);
        detail.setTextColor(TvTheme.TEXT_4);
        detail.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f);
        detail.setSingleLine(true);
        labels.addView(detail);

        TextView action = new TextView(this);
        action.setText("连接");
        action.setTextColor(TvTheme.ACCENT);
        action.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        row.addView(action);

        row.setOnClickListener(view -> authenticateStored(profile));
        return row;
    }

    private void openForm() {
        form.setVisibility(View.VISIBLE);
        initialFocus = hostField;
        if (hostField.getText().length() == 0) applyInitialFocus();
    }

    private void submitManual() {
        String host = hostField.getText().toString().trim();
        if (host.isEmpty()) {
            status.setText("请填写设备地址");
            hostField.requestFocus();
            return;
        }
        int port = 5666;
        String rawPort = portField.getText().toString().trim();
        if (!rawPort.isEmpty()) {
            try {
                port = Integer.parseInt(rawPort);
            } catch (NumberFormatException ignored) {
                status.setText("端口必须是数字");
                portField.requestFocus();
                return;
            }
        }
        boolean https = port == 5667;
        String user = userField.getText().toString().trim();
        String password = passwordField.getText().toString();
        if (user.isEmpty()) {
            status.setText("请填写用户名");
            userField.requestFocus();
            return;
        }
        ConnectionProfile profile = ConnectionProfile.create(
                "tv:" + host.toLowerCase(Locale.ROOT) + ":" + port + ":" + user,
                host, host, port, https, https, user, password);
        authenticateStored(profile);
    }

    private void authenticateStored(ConnectionProfile profile) {
        status.setText("正在连接 " + profile.host + "…");
        setFormEnabled(false);
        authClient.authenticate(this, profile, profile.password, new FnOsAuthClient.Callback() {
            @Override public void onSuccess(ConnectionProfile authenticatedProfile) {
                store.upsert(authenticatedProfile, true);
                openShell(authenticatedProfile);
            }

            @Override public void onError(String message) {
                status.setText(message == null || message.isEmpty() ? "连接失败" : message);
                setFormEnabled(true);
            }
        });
    }

    private void setFormEnabled(boolean enabled) {
        hostField.setEnabled(enabled);
        portField.setEnabled(enabled);
        userField.setEnabled(enabled);
        passwordField.setEnabled(enabled);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopPairing();
        authClient.cancel();
    }
}
