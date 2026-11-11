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
 * <p>A living-room remote is a poor text input device, so the primary path is
 * to reuse a connection the phone already authenticated: the TV lists the saved
 * profiles and signs in with the stored token. The manual form exists for a
 * television that has never been paired with a phone, and is deliberately kept
 * to four fields.
 */
public final class TvLoginActivity extends AppCompatActivity {
    private final FnOsAuthClient authClient = new FnOsAuthClient();

    private SecureProfileStore store;
    private LinearLayout profileList;
    private LinearLayout form;
    private TextView status;

    private EditText hostField;
    private EditText portField;
    private EditText userField;
    private EditText passwordField;

    /** The view the page wants focused once it is on screen. */
    @Nullable private View initialFocus;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        store = new SecureProfileStore(this);
        setContentView(buildUi());
        TvUi.hideSystemBars(this);
        renderProfiles();
    }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(TvUi.BG);
        root.setPadding(TvUi.dp(this, 56), TvUi.dp(this, 22),
                TvUi.dp(this, 56), TvUi.dp(this, 20));

        TextView brand = new TextView(this);
        brand.setText("fnAudio");
        brand.setTextColor(TvUi.TEXT);
        brand.setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f);
        brand.setTypeface(null, android.graphics.Typeface.BOLD);
        root.addView(brand);

        TextView tagline = new TextView(this);
        tagline.setText("连接到你的音乐库");
        tagline.setTextColor(TvUi.TEXT_3);
        tagline.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f);
        tagline.setPadding(0, TvUi.dp(this, 4), 0, TvUi.dp(this, 16));
        root.addView(tagline);

        ScrollView scroll = new ScrollView(this);
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(column);
        root.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        profileList = new LinearLayout(this);
        profileList.setOrientation(LinearLayout.VERTICAL);
        column.addView(profileList);

        form = buildForm();
        column.addView(form);

        status = new TextView(this);
        status.setTextColor(TvUi.TEXT_2);
        status.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        status.setPadding(0, TvUi.dp(this, 18), 0, 0);
        column.addView(status);

        return root;
    }

    private LinearLayout buildForm() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setVisibility(View.GONE);

        TextView heading = new TextView(this);
        heading.setText("新增连接");
        heading.setTextColor(TvUi.TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f);
        heading.setPadding(0, TvUi.dp(this, 8), 0, TvUi.dp(this, 10));
        box.addView(heading);

        hostField = input(box, "设备地址，例如 192.168.5.141", InputType.TYPE_CLASS_TEXT);
        portField = input(box, "端口（默认 5666）", InputType.TYPE_CLASS_NUMBER);
        userField = input(box, "用户名", InputType.TYPE_CLASS_TEXT);
        passwordField = input(box, "密码", InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        passwordField.setImeOptions(EditorInfo.IME_ACTION_DONE);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setPadding(0, TvUi.dp(this, 12), 0, 0);
        box.addView(actions);

        TextView submit = pill("连接", true);
        submit.setOnClickListener(view -> submitManual());
        actions.addView(submit);

        TextView cancel = pill("取消", false);
        LinearLayout.LayoutParams cancelParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cancelParams.leftMargin = TvUi.dp(this, 14);
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
        field.setHintTextColor(TvUi.TEXT_3);
        field.setTextColor(TvUi.TEXT);
        field.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
        field.setInputType(inputType);
        field.setSingleLine(true);
        field.setBackground(TvUi.rounded(TvUi.PANEL, 10f, this));
        field.setPadding(TvUi.dp(this, 16), TvUi.dp(this, 10),
                TvUi.dp(this, 16), TvUi.dp(this, 10));
        // On a television the keyboard belongs to an explicit OK press: wiring
        // it to focus alone means the soft keyboard covers the form the moment
        // the screen opens, which is what the first run of this page did. Touch
        // and click deliberately do not raise it either — a pointer lands on a
        // field to read it far more often than to type in it.
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
                TvUi.dp(this, 460), ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = TvUi.dp(this, 8);
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
        button.setTextColor(primary ? 0xFF071018 : TvUi.TEXT);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
        button.setTypeface(null, android.graphics.Typeface.BOLD);
        button.setGravity(Gravity.CENTER);
        button.setFocusable(true);
        button.setFocusableInTouchMode(false);
        button.setPadding(TvUi.dp(this, 30), TvUi.dp(this, 13),
                TvUi.dp(this, 30), TvUi.dp(this, 13));
        button.setBackground(TvUi.rounded(primary ? TvUi.ACCENT : TvUi.PANEL, 24f, this));
        button.setForeground(TvUi.focusRing(this, 24f));
        TvUi.applyFocusScale(button, 1.06f);
        return button;
    }

    private void renderProfiles() {
        profileList.removeAllViews();
        List<ConnectionProfile> profiles = store.list();
        form.setVisibility(View.GONE);

        if (profiles.isEmpty()) {
            TextView empty = new TextView(this);
            empty.setText("还没有已保存的连接，填写下面的信息即可开始。");
            empty.setTextColor(TvUi.TEXT_2);
            empty.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
            empty.setPadding(0, 0, 0, TvUi.dp(this, 22));
            profileList.addView(empty);
            openForm();
            return;
        }

        TextView heading = new TextView(this);
        heading.setText("选择连接");
        heading.setTextColor(TvUi.TEXT);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f);
        heading.setPadding(0, 0, 0, TvUi.dp(this, 12));
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
        params.topMargin = TvUi.dp(this, 22);
        addAnother.setOnClickListener(view -> openForm());
        profileList.addView(addAnother, params);

        // A television has no pointer to fall back on: with nothing focused the
        // first OK press only moves the highlight, so the most likely action —
        // sign in with the connection already stored — is focused up front.
        initialFocus = firstRow;
        applyInitialFocus();
    }

    /**
     * The window does its own focus assignment once it is attached, and it
     * picks the last focusable in the tree, so the row requested during
     * inflation loses the race. Re-applying the choice when the window gains
     * focus is what makes the first OK press land on "connect".
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
        row.setPadding(TvUi.dp(this, 24), TvUi.dp(this, 18),
                TvUi.dp(this, 24), TvUi.dp(this, 18));
        row.setBackground(TvUi.rounded(TvUi.PANEL, 12f, this));
        row.setForeground(TvUi.focusRing(this, 12f));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = TvUi.dp(this, 10);
        row.setLayoutParams(params);

        LinearLayout labels = new LinearLayout(this);
        labels.setOrientation(LinearLayout.VERTICAL);
        row.addView(labels, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView name = new TextView(this);
        name.setText(profile.name == null || profile.name.isEmpty() ? profile.host : profile.name);
        name.setTextColor(TvUi.TEXT);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 19f);
        labels.addView(name);

        TextView detail = new TextView(this);
        detail.setText(profile.host + ":" + profile.port + " · " + profile.username);
        detail.setTextColor(TvUi.TEXT_3);
        detail.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f);
        labels.addView(detail);

        TextView action = new TextView(this);
        action.setText("连接");
        action.setTextColor(TvUi.ACCENT);
        action.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        row.addView(action);

        row.setOnClickListener(view -> authenticate(profile));
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
        authenticate(profile);
    }

    private void authenticate(ConnectionProfile profile) {
        status.setText("正在连接 " + profile.host + "…");
        setFormEnabled(false);
        authClient.authenticate(this, profile, profile.password, new FnOsAuthClient.Callback() {
            @Override public void onSuccess(ConnectionProfile authenticatedProfile) {
                store.upsert(authenticatedProfile, true);
                Intent intent = new Intent(TvLoginActivity.this, TvMainActivity.class);
                intent.putExtra(TvMainActivity.EXTRA_PROFILE_ID, authenticatedProfile.id);
                startActivity(intent);
                finish();
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
        authClient.cancel();
    }
}
