package com.fnaudio.client.ui;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.activity.result.ActivityResultLauncher;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.PairingPayload;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.network.PairingClient;
import com.journeyapps.barcodescanner.ScanContract;
import com.journeyapps.barcodescanner.ScanOptions;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Hands one saved connection to a television.
 *
 * <p>The television shows a QR code holding its own address and a one-time
 * six-digit code; this screen reads that code with the camera and posts the
 * profile to it over the LAN. Typing the address and the digits by hand does the
 * same thing, which is what a phone without a camera - or a television and phone
 * on different subnets - falls back to.
 *
 * <p>The password never leaves the phone: {@code PairingTransfer} sends the long
 * token only.
 */
public final class PairingSendActivity extends AppCompatActivity {
    private static final String DEFAULT_PORT = "42001";

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final List<ConnectionProfile> saved = new ArrayList<>();
    /** The "已选择" marker of each row, index-aligned with {@link #saved}. */
    private final List<TextView> marks = new ArrayList<>();

    private EditText addressField;
    private EditText codeField;
    private LinearLayout profileList;
    private TextView status;
    private Button sendButton;

    @Nullable private ConnectionProfile selected;
    private boolean busy;

    /** zxing's own capture screen asks for the camera permission itself. */
    private final ActivityResultLauncher<ScanOptions> scanner =
            registerForActivityResult(new ScanContract(), result -> {
                if (result.getContents() == null) {
                    setStatus("已取消扫码");
                    return;
                }
                applyScanned(result.getContents());
            });

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_pairing_send);
        addressField = findViewById(R.id.pairingAddress);
        codeField = findViewById(R.id.pairingCode);
        profileList = findViewById(R.id.pairingProfiles);
        status = findViewById(R.id.pairingStatus);
        sendButton = findViewById(R.id.pairingSendButton);

        findViewById(R.id.pairingBackButton).setOnClickListener(view -> finish());
        findViewById(R.id.pairingScanButton).setOnClickListener(view -> scan());
        sendButton.setOnClickListener(view -> send());

        saved.addAll(new SecureProfileStore(this).list());
        renderProfiles();
    }

    private void scan() {
        ScanOptions options = new ScanOptions();
        options.setDesiredBarcodeFormats(ScanOptions.QR_CODE);
        options.setPrompt("对准电视上的二维码");
        options.setBeepEnabled(false);
        options.setOrientationLocked(false);
        options.setBarcodeImageEnabled(false);
        scanner.launch(options);
    }

    private void applyScanned(String contents) {
        try {
            PairingPayload payload = PairingPayload.parse(contents);
            addressField.setText(payload.host + ":" + payload.port);
            codeField.setText(payload.code);
            setStatus("已读到电视地址，选一个连接后发送");
        } catch (IllegalArgumentException notOurs) {
            setStatus(notOurs.getMessage() == null ? "这不是 fnAudio 的配对码" : notOurs.getMessage());
        }
    }

    private void renderProfiles() {
        profileList.removeAllViews();
        marks.clear();
        if (saved.isEmpty()) {
            TextView empty = new TextView(this);
            empty.setText("还没有保存的连接，先在登录页连接一次");
            empty.setTextColor(0xFFBFD0E4);
            empty.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f);
            profileList.addView(empty);
            sendButton.setEnabled(false);
            return;
        }
        for (ConnectionProfile profile : saved) {
            profileList.addView(profileRow(profile));
        }
        select(saved.get(0));
    }

    private View profileRow(final ConnectionProfile profile) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.VERTICAL);
        row.setPadding(dp(14), dp(10), dp(14), dp(10));
        row.setBackgroundResource(R.drawable.login_input);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(8);
        row.setLayoutParams(params);
        row.setOnClickListener(view -> select(profile));

        TextView name = new TextView(this);
        name.setText(profile.name == null || profile.name.isEmpty() ? profile.host : profile.name);
        name.setTextColor(0xFF171717);
        name.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f);
        row.addView(name);

        TextView detail = new TextView(this);
        detail.setText(profile.host + ":" + profile.port + " · " + profile.username);
        detail.setTextColor(0xFF6B7683);
        detail.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f);
        row.addView(detail);

        TextView mark = new TextView(this);
        mark.setText("已选择");
        mark.setTextColor(0xFF176BEF);
        mark.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f);
        mark.setGravity(Gravity.END);
        mark.setVisibility(View.GONE);
        row.addView(mark);

        marks.add(mark);
        return row;
    }

    private void select(ConnectionProfile profile) {
        selected = profile;
        int chosen = saved.indexOf(profile);
        for (int index = 0; index < marks.size(); index++) {
            boolean active = index == chosen;
            marks.get(index).setVisibility(active ? View.VISIBLE : View.GONE);
            View row = (View) marks.get(index).getParent();
            if (row != null) row.setAlpha(active ? 1f : 0.72f);
        }
    }

    private void send() {
        if (busy) return;
        PairingPayload payload = readPayload();
        if (payload == null) return;
        if (selected == null) {
            setStatus("先选一个要发送的连接");
            return;
        }
        final ConnectionProfile profile = selected;
        setBusy(true);
        setStatus("正在发送到 " + payload.host + ":" + payload.port + " …");
        io.execute(() -> {
            String failure = null;
            try {
                PairingClient.send(payload, profile);
            } catch (IOException error) {
                failure = error.getMessage();
            }
            final String message = failure;
            main.post(() -> {
                setBusy(false);
                setStatus(message == null
                        ? "已发送。电视会自己连上，这个页面可以关掉了。"
                        : message);
            });
        });
    }

    /**
     * Reads and validates the two manual fields.
     *
     * @return null after writing a message into the status line, so the caller
     *         has one place to stop
     */
    @Nullable
    private PairingPayload readPayload() {
        String address = addressField.getText().toString().trim();
        if (address.isEmpty()) {
            setStatus("请扫描二维码，或填写电视上显示的地址");
            return null;
        }
        String host = address;
        String portText = DEFAULT_PORT;
        int colon = address.lastIndexOf(':');
        if (colon > 0) {
            host = address.substring(0, colon);
            portText = address.substring(colon + 1);
        }
        int port;
        try {
            port = Integer.parseInt(portText.trim());
        } catch (NumberFormatException error) {
            setStatus("端口不是数字，格式是 地址:端口");
            return null;
        }
        String code = codeField.getText().toString().replaceAll("\\s", "");
        if (code.length() != 6) {
            setStatus("配对码是六位数字");
            return null;
        }
        return PairingPayload.of(host.trim(), port, code);
    }

    private void setBusy(boolean value) {
        busy = value;
        sendButton.setEnabled(!value);
    }

    private void setStatus(String message) {
        status.setText(TextUtils.isEmpty(message) ? "" : message);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
    }
}
