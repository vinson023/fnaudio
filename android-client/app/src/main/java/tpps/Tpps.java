package tpps;

import go.Seq;

public final class Tpps {
    static {
        Seq.touch();
        _init();
    }

    private Tpps() {
    }

    private static native void _init();

    public static native String applyConfigJSON(String config);

    public static native long getConnectStatus();

    public static native String getVersion();

    public static native long startWithPort(long port);

    public static native long startWithSocket(String socket);

    public static native void stop();

    public static void touch() {
    }
}
