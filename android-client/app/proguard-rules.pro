# The release build currently keeps the WebView bridge names stable.
-keepclassmembers class com.fnaudio.client.web.NativePlaybackBridge {
    @android.webkit.JavascriptInterface <methods>;
}
