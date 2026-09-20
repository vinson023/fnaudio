package com.fnaudio.client.ui;

import android.content.ComponentName;
import android.media.MediaMetadata;
import android.media.browse.MediaBrowser;
import android.media.session.MediaController;
import android.media.session.PlaybackState;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.fnaudio.client.R;

/** Standalone diagnostic client for the exported fnOS MediaBrowser service. */
public final class FnOsMediaSessionActivity extends AppCompatActivity {
    private static final ComponentName FNOS_SERVICE = new ComponentName(
            "com.trim.app", "com.ryanheise.audioservice.AudioService");

    private TextView status;
    private TextView metadata;
    private MediaBrowser browser;
    private MediaController controller;
    private final MediaController.Callback controllerCallback = new MediaController.Callback() {
        @Override public void onPlaybackStateChanged(PlaybackState state) { updateControllerState(); }
        @Override public void onMetadataChanged(MediaMetadata data) { updateControllerState(); }
    };

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setTitle("飞牛 APP MediaSession 测试");
        setContentView(buildContent());
        connect();
    }

    private View buildContent() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 40, 32, 32);

        TextView title = new TextView(this);
        title.setText("飞牛 APP MediaSession 测试版");
        title.setTextSize(22);
        root.addView(title, new LinearLayout.LayoutParams(-1, -2));

        status = new TextView(this);
        status.setText("正在连接飞牛 APP 音频服务…");
        status.setPadding(0, 18, 0, 18);
        root.addView(status, new LinearLayout.LayoutParams(-1, -2));

        metadata = new TextView(this);
        metadata.setText("当前媒体：未读取");
        metadata.setTextSize(17);
        root.addView(metadata, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        addButton(controls, "上一首", v -> dispatch(c -> c.getTransportControls().skipToPrevious()));
        addButton(controls, "播放", v -> dispatch(c -> c.getTransportControls().play()));
        addButton(controls, "暂停", v -> dispatch(c -> c.getTransportControls().pause()));
        addButton(controls, "下一首", v -> dispatch(c -> c.getTransportControls().skipToNext()));
        addButton(controls, "停止", v -> dispatch(c -> c.getTransportControls().stop()));
        root.addView(controls, new LinearLayout.LayoutParams(-1, -2));

        Button refresh = new Button(this);
        refresh.setText("重新连接");
        refresh.setOnClickListener(v -> reconnect());
        root.addView(refresh, new LinearLayout.LayoutParams(-1, -2));

        TextView note = new TextView(this);
        note.setText("本测试版独立于正常 fnAudio，控制请求直接发送到飞牛 APP 的 MediaSession。\n不会启动 fnAudio 自己的播放服务。");
        note.setPadding(0, 24, 0, 0);
        root.addView(note, new LinearLayout.LayoutParams(-1, -2));
        return new ScrollView(this) {{ addView(root); }};
    }

    private void addButton(LinearLayout row, String label, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(label);
        button.setOnClickListener(listener);
        row.addView(button, new LinearLayout.LayoutParams(0, -2, 1));
    }

    private interface ControllerAction { void run(MediaController controller); }

    private void dispatch(ControllerAction action) {
        if (controller == null) {
            status.setText("尚未连接飞牛 APP MediaSession");
            return;
        }
        action.run(controller);
        updateControllerState();
    }

    private void connect() {
        browser = new MediaBrowser(this, FNOS_SERVICE, new MediaBrowser.ConnectionCallback() {
            @Override public void onConnected() {
                controller = new MediaController(FnOsMediaSessionActivity.this, browser.getSessionToken());
                controller.registerCallback(controllerCallback);
                status.setText("已连接：" + browser.getRoot());
                updateControllerState();
            }
            @Override public void onConnectionFailed() { status.setText("连接失败：请确认飞牛 APP 已启动并已登录"); }
            @Override public void onConnectionSuspended() { status.setText("连接中断"); }
        }, new Bundle());
        browser.connect();
    }

    private void reconnect() {
        if (controller != null) { controller.unregisterCallback(controllerCallback); controller = null; }
        if (browser != null) browser.disconnect();
        status.setText("正在重新连接…");
        connect();
    }

    private void updateControllerState() {
        if (controller == null) return;
        MediaMetadata data = controller.getMetadata();
        PlaybackState state = controller.getPlaybackState();
        String title = data == null ? "未知" : String.valueOf(data.getText(MediaMetadata.METADATA_KEY_TITLE));
        String artist = data == null ? "" : String.valueOf(data.getText(MediaMetadata.METADATA_KEY_ARTIST));
        String playback = state == null ? "未知" : stateName(state.getState());
        metadata.setText("当前媒体：" + title + (artist.isEmpty() ? "" : "\n" + artist) + "\n状态：" + playback);
    }

    private String stateName(int state) {
        switch (state) {
            case PlaybackState.STATE_PLAYING: return "播放中";
            case PlaybackState.STATE_PAUSED: return "已暂停";
            case PlaybackState.STATE_BUFFERING: return "缓冲中";
            case PlaybackState.STATE_STOPPED: return "已停止";
            case PlaybackState.STATE_ERROR: return "错误";
            default: return "空闲";
        }
    }

    @Override protected void onDestroy() {
        if (controller != null) controller.unregisterCallback(controllerCallback);
        if (browser != null) browser.disconnect();
        super.onDestroy();
    }
}
