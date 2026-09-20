package com.fnaudio.client.network;

import android.annotation.SuppressLint;
import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONObject;

import java.net.ServerSocket;
import java.util.Locale;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

import go.Seq;
import tpps.Tpps;

final class TppsTunnel {
    interface Callback {
        void onReady(int port);
        void onError(String message);
    }

    private static final String TAG = "FnConnectRelay";
    private static volatile TppsTunnel instance;

    static TppsTunnel get(Context context) {
        if (instance == null) {
            synchronized (TppsTunnel.class) {
                if (instance == null) instance = new TppsTunnel(context.getApplicationContext());
            }
        }
        return instance;
    }

    // This process-scoped tunnel must outlive LoginActivity. Only the
    // application context is retained, so the StaticFieldLeak warning is a false positive.
    @SuppressLint("StaticFieldLeak")
    private final Context applicationContext;
    private final Handler main = new Handler(Looper.getMainLooper());
    // Start/cancel commands supersede older work. Keep only one queued action
    // behind the in-flight native call so rapid connection switches stay bounded.
    private final ExecutorService worker = new ThreadPoolExecutor(
            1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(1),
            new ThreadPoolExecutor.DiscardOldestPolicy());
    private int activePort;
    private String activeServerId = "";
    private boolean nativeStarted;
    private long generation;
    private Runnable pendingReadyPoll;

    private TppsTunnel(Context applicationContext) {
        this.applicationContext = applicationContext;
    }

    synchronized void start(JSONObject config, Callback callback) {
        clearReadyPoll();
        long requestGeneration = ++generation;
        // JSONObject is mutable and the caller commonly reuses the request
        // object while switching profiles. Snapshot it before crossing to the
        // worker so a later UI mutation cannot change an already queued native
        // session start.
        final JSONObject configSnapshot;
        try {
            configSnapshot = config == null ? new JSONObject() : new JSONObject(config.toString());
        } catch (RuntimeException error) {
            deliverError(requestGeneration, callback, "FN Connect 配置无法读取");
            return;
        }
        enqueueLatest(() -> startOnWorker(configSnapshot, requestGeneration, callback));
    }

    synchronized void cancel() {
        clearReadyPoll();
        ++generation;
        enqueueLatest(this::stopNativeSession);
    }

    private synchronized void enqueueLatest(Runnable action) {
        // DiscardOldestPolicy bounds the queue, but it can discard a queued
        // stop when a newer start arrives. Every queued action is already
        // superseded by the newest generation, so clear the old work first;
        // the newest action is then the only pending native transition.
        worker.getQueue().clear();
        worker.execute(action);
    }

    private synchronized void clearReadyPoll() {
        if (pendingReadyPoll != null) {
            main.removeCallbacks(pendingReadyPoll);
            pendingReadyPoll = null;
        }
    }

    private void startOnWorker(JSONObject config, long requestGeneration, Callback callback) {
        if (!isCurrent(requestGeneration)) return;
        boolean nativeStartAttempted = false;
        if (!supportsArm64()) {
            deliverError(requestGeneration, callback, "当前设备架构不支持 FN Connect 中继");
            return;
        }
        try {
            // Seq loads the ARM64 JNI library. Keep this behind supportsArm64()
            // so translated x86 emulator processes never touch the native runtime.
            Seq.setContext(applicationContext);
            String requestedServerId = stringField(config, "visit_server").trim();
            if (!requestedServerId.isEmpty() && requestedServerId.equals(activeServerId)
                    && activePort > 0 && Tpps.getConnectStatus() == 1) {
                deliverReady(requestGeneration, callback, activePort);
                return;
            }

            if (!isCurrent(requestGeneration)) return;
            // Calling stop before the Go engine starts can terminate the
            // native process instead of raising a catchable Java exception.
            stopNativeSession();
            activePort = 0;
            activeServerId = "";
            JSONObject applied = new JSONObject(Tpps.applyConfigJSON(config.toString()));
            if (!booleanField(applied, "ok", false)) {
                deliverError(requestGeneration, callback, "Tpps 配置未被接受");
                return;
            }
            if (!isCurrent(requestGeneration)) {
                stopNativeSession();
                return;
            }
            int port = availableLoopbackPort();
            nativeStartAttempted = true;
            long startResult = Tpps.startWithPort(port);
            if (startResult < 0) {
                // A native start may allocate process-local state before
                // returning a failure code. Clean up only after the start
                // call has actually been attempted; stopping before that
                // point can terminate an unrelated native process.
                stopNativeSessionAfterStartAttempt();
                deliverError(requestGeneration, callback, "Tpps 隧道启动失败（" + startResult + "）");
                return;
            }
            nativeStarted = true;
            if (!isCurrent(requestGeneration)) {
                stopNativeSession();
                return;
            }
            waitForReady(port, requestedServerId, requestGeneration, callback, 0);
        } catch (Throwable error) {
            Log.w(TAG, "relay unavailable: " + error.getClass().getSimpleName());
            if (nativeStartAttempted) stopNativeSessionAfterStartAttempt();
            if (isCurrent(requestGeneration)) {
                stopNativeSession();
                activePort = 0;
                activeServerId = "";
            }
            deliverError(requestGeneration, callback, "无法启动 FN Connect 中继：" + error.getClass().getSimpleName());
        }
    }

    private void waitForReady(int port, String serverId, long requestGeneration,
                              Callback callback, int attempt) {
        if (!isCurrent(requestGeneration)) return;
        try {
            if (Tpps.getConnectStatus() == 1) {
                clearReadyPoll();
                if (!isCurrent(requestGeneration)) return;
                activePort = port;
                activeServerId = serverId;
                deliverReady(requestGeneration, callback, port);
                return;
            }
        } catch (Throwable error) {
            clearReadyPoll();
            if (isCurrent(requestGeneration)) {
                stopNativeSession();
                activePort = 0;
                activeServerId = "";
            }
            deliverError(requestGeneration, callback, "FN Connect 中继状态读取失败");
            return;
        }
        if (attempt >= 48) {
            clearReadyPoll();
            if (isCurrent(requestGeneration)) {
                stopNativeSession();
                activePort = 0;
                activeServerId = "";
                deliverError(requestGeneration, callback, "FN Connect 中继连接超时");
            }
            return;
        }
        Runnable poll = () -> enqueueLatestIfCurrent(requestGeneration,
                () -> waitForReady(port, serverId, requestGeneration, callback, attempt + 1));
        synchronized (this) {
            if (generation != requestGeneration) return;
            pendingReadyPoll = poll;
        }
        main.postDelayed(poll, 250L);
    }

    private synchronized boolean isCurrent(long requestGeneration) {
        return generation == requestGeneration;
    }

    private synchronized void enqueueLatestIfCurrent(long requestGeneration, Runnable action) {
        if (generation != requestGeneration) return;
        worker.getQueue().clear();
        worker.execute(action);
    }

    private void deliverReady(long requestGeneration, Callback callback, int port) {
        main.post(() -> {
            if (isCurrent(requestGeneration)) callback.onReady(port);
        });
    }

    private void deliverError(long requestGeneration, Callback callback, String message) {
        main.post(() -> {
            if (isCurrent(requestGeneration)) callback.onError(message);
        });
    }

    private void stopNativeSession() {
        if (!nativeStarted) return;
        try {
            Tpps.stop();
        } catch (Throwable error) {
            Log.w(TAG, "relay stop failed: " + error.getClass().getSimpleName());
        } finally {
            nativeStarted = false;
        }
    }

    private void stopNativeSessionAfterStartAttempt() {
        try {
            Tpps.stop();
        } catch (Throwable error) {
            Log.w(TAG, "relay stop after failed start: " + error.getClass().getSimpleName());
        } finally {
            nativeStarted = false;
        }
    }

    private static boolean supportsArm64() {
        String runtimeArch = System.getProperty("os.arch", "").toLowerCase(Locale.ROOT);
        boolean nativeRuntime = runtimeArch.contains("aarch64") || runtimeArch.contains("arm64");
        return nativeRuntime && Build.SUPPORTED_ABIS.length > 0
                && "arm64-v8a".equals(Build.SUPPORTED_ABIS[0]);
    }

    private static int availableLoopbackPort() throws Exception {
        try (ServerSocket socket = new ServerSocket(0, 1, java.net.InetAddress.getLoopbackAddress())) {
            return socket.getLocalPort();
        }
    }

    private static String stringField(JSONObject object, String key) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof String ? (String) value : "";
    }

    private static boolean booleanField(JSONObject object, String key, boolean fallback) {
        Object value = object == null ? null : object.opt(key);
        return value instanceof Boolean ? (Boolean) value : fallback;
    }
}
