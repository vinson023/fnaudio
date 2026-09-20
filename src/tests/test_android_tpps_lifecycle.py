import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
TPPS_TUNNEL = ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "TppsTunnel.java"


class AndroidTppsLifecycleTests(unittest.TestCase):
    def test_native_stop_is_guarded_by_a_started_session(self):
        source = TPPS_TUNNEL.read_text(encoding="utf-8")
        self.assertIn("if (!nativeStarted) return;", source)
        self.assertEqual(source.count("Tpps.stop();"), 2)
        self.assertIn("nativeStarted = true;", source)
        self.assertIn("nativeStarted = false;", source)

    def test_failed_native_start_attempt_is_cleaned_without_unconditional_pre_start_stop(self):
        source = TPPS_TUNNEL.read_text(encoding="utf-8")
        self.assertIn("boolean nativeStartAttempted = false;", source)
        self.assertIn("nativeStartAttempted = true;", source)
        self.assertIn("stopNativeSessionAfterStartAttempt();", source)
        failed_start = source[source.index("long startResult = Tpps.startWithPort"):source.index("nativeStarted = true;", source.index("long startResult = Tpps.startWithPort"))]
        self.assertIn("if (startResult < 0)", failed_start)
        self.assertIn("stopNativeSessionAfterStartAttempt();", failed_start)
        self.assertIn("private void stopNativeSessionAfterStartAttempt()", source)

    def test_tpps_native_work_queue_discards_superseded_requests(self):
        source = TPPS_TUNNEL.read_text(encoding="utf-8")
        self.assertIn("new ArrayBlockingQueue<>(1)", source)
        self.assertIn("new ThreadPoolExecutor.DiscardOldestPolicy()", source)
        self.assertIn("worker.getQueue().clear();", source)
        self.assertIn("private synchronized void enqueueLatest(Runnable action)", source)
        self.assertIn("private synchronized void enqueueLatestIfCurrent(long requestGeneration, Runnable action)", source)
        self.assertIn("enqueueLatestIfCurrent(requestGeneration", source)
        self.assertNotIn("Executors.newSingleThreadExecutor()", source)

    def test_secure_profile_store_serializes_cross_instance_read_modify_write(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "data" / "SecureProfileStore.java").read_text(encoding="utf-8")
        self.assertIn("private static final Object STATE_LOCK = new Object();", source)
        self.assertGreaterEqual(source.count("synchronized (STATE_LOCK)"), 6)
        self.assertNotIn("public synchronized ", source)
        self.assertIn("MAX_ENCRYPTED_PAYLOAD_CHARS", source)
        self.assertIn("MAX_CLEAR_PAYLOAD_BYTES", source)
        self.assertIn("MAX_PROFILES = 128", source)
        self.assertIn("Math.min(rows.length(), MAX_PROFILES)", source)
        oversized_branch = source[
            source.index("if (encrypted.length() > MAX_ENCRYPTED_PAYLOAD_CHARS)"):
            source.index("try {", source.index("if (encrypted.length() > MAX_ENCRYPTED_PAYLOAD_CHARS)"))
        ]
        self.assertIn("unreadableCiphertext = encrypted;", oversized_branch)

    def test_login_resolver_does_not_evict_tls_connections_on_main_thread(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        self.assertNotIn("connectionPool().evictAll()", source)
        self.assertIn("client.dispatcher().executorService().shutdown();", source)
        self.assertIn("public void close()", source)

    def test_http_client_limits_unpinned_self_signed_trust_to_authentication_bootstrap(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "HttpClientFactory.java").read_text(encoding="utf-8")
        guarded = source[source.index("if (profile != null && profile.https && profile.trustSelfSigned"):
                          source.index("        return builder.build();")]
        self.assertIn("!CertificatePin.normalize(profile.certificatePinSha256).isEmpty()", guarded)
        self.assertIn("certificate pin is missing or invalid", source)
        self.assertIn("if (!CertificatePin.matches(normalizedPin, chain[0]))", source)
        bootstrap = source[source.index("public static OkHttpClient createAuthenticationClient"):source.index("    /**\n     * Creates the media client")]
        self.assertIn("!CertificatePin.normalize(profile.certificatePinSha256).isEmpty()", bootstrap)
        self.assertIn("trustFirstUseSelfSigned(builder);", bootstrap)
        auth = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnOsAuthClient.java").read_text(encoding="utf-8")
        self.assertIn("HttpClientFactory.createAuthenticationClient(context, profile)", auth)

    def test_resolver_handles_close_race_during_call_submission(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        self.assertIn("import java.util.concurrent.RejectedExecutionException;", source)
        self.assertIn("if (generation < 0L)", source)
        self.assertIn("catch (RejectedExecutionException error)", source)
        self.assertIn("private boolean closed;", source)
        self.assertIn("if (closed) return -1L;", source)
        self.assertIn('main.post(() -> callback.onError("FN Connect 解析器已关闭"));', source)

    def test_resolver_close_cancels_owned_work_before_dispatcher_shutdown(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        close = source[source.index("public void close()"):source.index("private boolean isActive", source.index("public void close()"))]
        self.assertIn("++callGeneration", close)
        self.assertIn("relayConfigClient.cancel()", close)
        self.assertIn("tunnel.cancel()", close)
        self.assertIn("activeCall.cancel()", close)
        self.assertIn("activeProbeSocket.close()", close)
        self.assertNotIn("\n        cancel();", close)
        self.assertLess(close.index("activeCall.cancel()"), close.index("client.dispatcher().executorService().shutdown()"))

    def test_resolver_delivers_invalid_id_errors_on_the_main_handler(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        invalid_branch = source[source.index('if (!fnId.matches('):source.index('JSONObject payload', source.index('if (!fnId.matches('))]
        self.assertIn('deliver(generation, () -> callback.onError("FN ID 格式不正确"));', invalid_branch)
        self.assertNotIn('replaceActiveWork(null)', invalid_branch)

    def test_resolver_reserves_generation_before_call_construction_and_attaches_atomically(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        resolve = source[source.index("public void resolve(String rawFnId, Mode mode"):
                         source.index("private static String readBoundedText", source.index("public void resolve(String rawFnId, Mode mode"))]
        self.assertLess(resolve.index("replaceActiveWork(null)"), resolve.index("client.newCall(request)"))
        self.assertIn("if (!attachActiveCall(call, generation))", resolve)
        attach = source[source.index("private boolean attachActiveCall"):
                        source.index("public void close()", source.index("private boolean attachActiveCall"))]
        self.assertIn("callGeneration != generation", attach)
        self.assertIn("call.cancel();", attach)

    def test_relay_config_handles_dispatcher_shutdown_during_call_submission(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectRelayConfigClient.java").read_text(encoding="utf-8")
        self.assertIn("import java.util.concurrent.RejectedExecutionException;", source)
        self.assertIn("catch (RejectedExecutionException error)", source)
        self.assertIn("if (finish(call)) callback.onError", source)

    def test_relay_config_keeps_response_call_cancellable_until_bounded_body_read_finishes(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectRelayConfigClient.java").read_text(encoding="utf-8")
        response = source[source.index("public void onResponse"):source.index("private static String readBoundedText")]
        self.assertIn("if (!isActive(completedCall))", response)
        self.assertIn("String text = readBoundedText(responseBody, MAX_RESPONSE_BYTES);", response)
        self.assertLess(response.index("readBoundedText(responseBody, MAX_RESPONSE_BYTES)"), response.index("if (finish(completedCall))"))
        self.assertIn("private boolean isActive(Call call)", source)

    def test_playback_service_handles_dispatcher_shutdown_during_remote_submission(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("import java.util.concurrent.RejectedExecutionException;", source)
        self.assertGreaterEqual(source.count("catch (RejectedExecutionException error)"), 3)
        self.assertIn("remotePollInFlight = false;", source)
        self.assertIn("onRemoteEventStreamEnded(call);", source)

    def test_playback_service_tracks_and_cancels_remote_commands_when_session_changes(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("MAX_REMOTE_COMMAND_CALLS = 16", source)
        self.assertIn("private final Set<Call> remoteCommandCalls = new HashSet<>();", source)
        self.assertIn("if (!trackRemoteCommandCall(commandCall))", source)
        self.assertIn("completeRemoteCommandCall(call);", source)
        self.assertIn("private void cancelRemoteCommandRequests()", source)
        self.assertIn("calls = new ArrayList<>(remoteCommandCalls);", source)
        self.assertIn("if (remoteCommandCalls.size() >= MAX_REMOTE_COMMAND_CALLS) return false;", source)
        self.assertGreaterEqual(source.count("cancelRemoteCommandRequests();"), 3)

    def test_main_activity_handles_dispatcher_shutdown_during_native_request(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("import java.util.concurrent.RejectedExecutionException;", source)
        self.assertIn("nativeHttpCalls.remove(safeRequestId, call);", source)
        self.assertIn("原生网络服务正在关闭，请稍后重试", source)

    def test_main_activity_enforces_native_http_call_limit_before_accepting_call_n_plus_one(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("rejected = nativeHttpCalls.size() > MAX_NATIVE_HTTP_CALLS;", source)
        self.assertIn("replacement reuses an existing slot", source)

    def test_resolver_cancel_closes_active_direct_probe_socket(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        self.assertIn("private Socket activeProbeSocket", source)
        self.assertIn("activeProbeSocket.close()", source)
        self.assertIn("private boolean isReachable(String host, int port, long generation)", source)
        self.assertIn("if (callGeneration != generation) return false;", source)

    def test_new_resolve_replaces_relay_tunnel_and_direct_probe_work_together(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        self.assertIn("final long generation = replaceActiveWork(null);", source)
        self.assertIn("if (!attachActiveCall(call, generation))", source)
        self.assertIn("public void cancel() {\n        replaceActiveWork(null);", source)
        replacement = source[source.index("private long replaceActiveWork("):source.index("public void close()")]
        self.assertIn("relayConfigClient.cancel();", replacement)
        self.assertIn("tunnel.cancel();", replacement)
        self.assertIn("activeProbeSocket.close()", replacement)
        self.assertIn("activeCall = replacement;", replacement)

    def test_direct_fn_connect_probes_have_a_total_time_budget(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        self.assertIn("DIRECT_PROBE_BUDGET_MS = 8000L", source)
        self.assertIn("long deadlineElapsedRealtime = SystemClock.elapsedRealtime() + DIRECT_PROBE_BUDGET_MS;", source)
        self.assertIn("deadlineElapsedRealtime - SystemClock.elapsedRealtime()", source)
        self.assertIn("Math.min(DIRECT_PROBE_TIMEOUT_MS, Math.max(1L, remainingMs))", source)

    def test_bounded_android_response_readers_handle_zero_byte_reads(self):
        files = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java",
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectRelayConfigClient.java",
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java",
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java",
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "MainActivity.java",
        )
        for path in files:
            source = path.read_text(encoding="utf-8")
            self.assertIn("if (count == 0) continue;", source, path.name)

    def test_authenticated_bitmap_loader_bounds_pending_downloads(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        self.assertIn("MAX_PENDING_LOADS = 16", source)
        self.assertIn("new ArrayBlockingQueue<>(MAX_PENDING_LOADS)", source)
        self.assertIn("new ThreadPoolExecutor.AbortPolicy()", source)
        self.assertIn("pendingFutures.remove(future);", source)
        self.assertIn("MAX_TEMP_FILE_AGE_MS", source)
        self.assertIn("now - file.lastModified() > MAX_TEMP_FILE_AGE_MS", source)

    def test_authenticated_bitmap_loader_cancels_underlying_artwork_calls(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        self.assertIn("ConcurrentHashMap<SettableFuture<Bitmap>, Call> activeCalls", source)
        self.assertIn("future.addListener", source)
        self.assertIn("activeCalls.remove(future)", source)
        self.assertIn("Call call = httpClient.newCall", source)
        self.assertIn("call.cancel();", source)
        self.assertIn("activeCalls.clear();", source)

    def test_authenticated_bitmap_loader_does_not_repopulate_cache_after_shutdown(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        method = source[source.index("private void writeCached") : source.index("private File cacheFile")]
        self.assertIn("synchronized (lifecycleLock)", method)
        self.assertIn("if (shutdown) return;", method)
        self.assertIn("if (shutdown || !temporary.renameTo(target))", method)
        self.assertLess(method.index("if (shutdown || !temporary.renameTo(target))"), method.index("pruneCache();"))

    def test_authenticated_bitmap_loader_rejects_cross_origin_network_artwork(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        method = source[source.index("public ListenableFuture<Bitmap> loadBitmap") : source.index("public void shutdown")]
        self.assertIn('if (uri == null) return failedFuture("Artwork URI is missing");', method)
        self.assertIn('if (isHttpUri(uri)) return failedFuture("Artwork URI is outside the active server");', method)
        self.assertIn("private static boolean isHttpUri(Uri uri)", source)
        self.assertIn("private static ListenableFuture<Bitmap> failedFuture", source)

    def test_authenticated_bitmap_loader_does_not_hit_expired_cache_entries(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        self.assertIn("now - file.lastModified() > MAX_CACHE_AGE_MS", source)
        self.assertIn("file.delete();", source)
        self.assertIn("file.setLastModified(now);", source)

    def test_authenticated_bitmap_loader_reads_cache_size_from_open_descriptor(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        method = source[source.index("private byte[] readCached") : source.index("private void writeCached")]
        self.assertIn("try (FileInputStream input = new FileInputStream(file))", method)
        self.assertIn("long size = input.getChannel().size();", method)
        self.assertIn("if (size <= 0 || size > MAX_ARTWORK_BYTES) return null;", method)
        self.assertIn("new byte[(int) size]", method)
        self.assertNotIn("new byte[(int) file.length()]", method)

    def test_authenticated_bitmap_loader_touches_cache_before_opening_descriptor(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        method = source[source.index("private byte[] readCached") : source.index("private void writeCached")]
        touch = method.index("file.setLastModified(now);")
        open_descriptor = method.index("try (FileInputStream input = new FileInputStream(file))")
        self.assertLess(touch, open_descriptor)

    def test_authenticated_cover_cache_reclaims_temp_files_and_bounds_entry_count(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "AuthenticatedCoverCache.java"
        ).read_text(encoding="utf-8")
        self.assertIn("MAX_ENTRIES = 256", source)
        self.assertIn("name.contains(\".tmp.\")", source)
        self.assertIn("Arrays.sort(ordered, Comparator.comparingLong(File::lastModified))", source)
        self.assertIn("remaining <= MAX_ENTRIES", source)
        self.assertIn("MAX_KEY_CHARS = 4096", source)
        self.assertIn("if (!validKey(scope) || !validKey(key)) return null", source)
        self.assertIn("if (!validKey(scope) || !validKey(key) || body == null", source)
        self.assertIn("input = new FileInputStream(file);", source)
        self.assertIn("long size = input.getChannel().size();", source)
        self.assertIn("if (size <= 0 || size > MAX_ENTRY_BYTES)", source)
        self.assertNotIn("while (total > MAX_BYTES && files.length > 0)", source)

    def test_authenticated_cover_cache_serializes_recency_touch_with_atomic_replace(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "AuthenticatedCoverCache.java"
        ).read_text(encoding="utf-8")
        self.assertIn("private static final Object CACHE_LOCK = new Object();", source)
        open_method = source[source.index("@Nullable InputStream open") : source.index("void put")]
        write_method = source[source.index("private void write") : source.index("private File fileFor")]
        self.assertIn("synchronized (CACHE_LOCK)", open_method)
        self.assertIn("file.setLastModified(System.currentTimeMillis());", open_method)
        self.assertIn("synchronized (CACHE_LOCK)", write_method)
        self.assertLess(
            write_method.index("synchronized (CACHE_LOCK)"),
            write_method.index("temporary.renameTo(target)"),
        )

    def test_shared_artwork_caches_protect_cross_activity_replacements(self):
        loader = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        cover = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "AuthenticatedCoverCache.java"
        ).read_text(encoding="utf-8")
        self.assertIn("private static final Object ARTWORK_CACHE_LOCK = new Object();", loader)
        read_method = loader[loader.index("private byte[] readCached"):loader.index("private void writeCached")]
        write_method = loader[loader.index("private void writeCached"):loader.index("private File cacheFile")]
        prune_method = loader[loader.index("private void pruneCache"):loader.index("private boolean isAuthenticatedOrigin")]
        self.assertIn("synchronized (ARTWORK_CACHE_LOCK)", read_method)
        self.assertIn("synchronized (ARTWORK_CACHE_LOCK)", write_method)
        self.assertIn("synchronized (ARTWORK_CACHE_LOCK)", prune_method)
        self.assertIn("catch (OutOfMemoryError ignored)", read_method)
        self.assertIn("private static final Object CACHE_LOCK = new Object();", cover)
        self.assertNotIn("private final Object cacheLock", cover)

    def test_authenticated_artwork_caches_are_scoped_to_connection_profile(self):
        loader = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        cover = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "AuthenticatedCoverCache.java"
        ).read_text(encoding="utf-8")
        main = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "MainActivity.java"
        ).read_text(encoding="utf-8")
        self.assertIn('profileScope.length() + ":" + profileScope + uri.toString()', loader)
        self.assertIn('open(String scope, String key)', cover)
        self.assertIn('put(String scope, String key, byte[] body)', cover)
        self.assertIn('sha256(scope.length() + ":" + scope + key)', cover)
        self.assertIn('thumbnailCache.open(profileCacheScope(requestProfile), uri.toString())', main)
        self.assertIn('thumbnailCache.put(profileCacheScope(requestProfile), uri.toString(), bytes)', main)

    def test_cancelled_artwork_load_does_not_write_or_decode_after_download(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        method = source[source.index("public ListenableFuture<Bitmap> loadBitmap") : source.index("public void shutdown")]
        self.assertGreaterEqual(method.count("if (future.isCancelled()) return;"), 3)
        self.assertIn("bitmap.recycle();", method)
        self.assertLess(method.index("if (future.isCancelled()) return;\n                        if (data != null) writeCached"), method.index("ArtworkBitmapDecoder.decode(data)"))

    def test_bitmap_loader_recycles_bitmap_when_future_delivery_is_rejected(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("if (!future.set(bitmap)) bitmap.recycle();"), 2)

    def test_main_activity_captures_response_media_type_before_closing_thumbnail_body(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "MainActivity.java"
        ).read_text(encoding="utf-8")
        body_line = source.index("ResponseBody body = response.body();")
        media_line = source.index("MediaType mediaType = body == null ? null : body.contentType();")
        close_line = source.index("response.close();", media_line)
        code_line = source.index("final int responseCode = response.code();")
        headers_line = source.index("final Map<String, String> responseHeaderValues = responseHeaders(response.headers());")
        status_line = source.index("setStatusCodeAndReasonPhrase(responseCode", body_line)
        self.assertLess(body_line, media_line)
        self.assertLess(code_line, close_line)
        self.assertLess(headers_line, close_line)
        self.assertLess(media_line, close_line)
        self.assertGreater(status_line, close_line)

    def test_main_activity_closes_intercepted_response_when_webview_handoff_fails(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "MainActivity.java"
        ).read_text(encoding="utf-8")
        response_line = source.index("response = client.newCall(builder.build()).execute();")
        handoff_line = source.index("responseOwnedByWebView = true;", response_line)
        cleanup_line = source.index("if (response != null && !responseOwnedByWebView) response.close();", response_line)
        thumbnail_close_line = source.index("response.close();", response_line)
        null_line = source.index("response = null;", thumbnail_close_line)
        self.assertLess(response_line, handoff_line)
        self.assertLess(thumbnail_close_line, null_line)
        self.assertLess(handoff_line, cleanup_line)

    def test_main_activity_rejects_stale_intercept_response_after_destroy(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "MainActivity.java"
        ).read_text(encoding="utf-8")
        response_line = source.index("response = client.newCall(builder.build()).execute();")
        current_check = source.index("if (!isCurrentWebResourceClient(client)) return null;", response_line)
        handoff_line = source.index("responseOwnedByWebView = true;", response_line)
        helper = source[source.index("private boolean isCurrentWebResourceClient") : source.index("private static boolean isListThumbnail")]
        self.assertLess(response_line, current_check)
        self.assertLess(current_check, handoff_line)
        self.assertIn("synchronized (nativeHttpCalls)", helper)
        self.assertIn("!destroyed && webResourceClient == client", helper)

    def test_main_activity_rechecks_lifecycle_for_bundled_and_cached_fast_paths(self):
        source = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "ui" / "MainActivity.java"
        ).read_text(encoding="utf-8")
        start = source.index("private WebResourceResponse interceptAuthenticatedGet")
        end = source.index("private static boolean isListThumbnail", start)
        block = source[start:end]
        self.assertIn("if (!isCurrentWebResourceClient(client)) return null;", block)
        self.assertIn("if (isCurrentWebResourceClient(client)) return bundled;", block)
        self.assertIn("closeWebResourceResponse(bundled);", block)
        self.assertIn("if (!isCurrentWebResourceClient(client)) {", block)
        self.assertIn("cached.close();", block)

    def test_remote_artwork_decode_has_a_shared_pixel_budget(self):
        decoder = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "ArtworkBitmapDecoder.java"
        ).read_text(encoding="utf-8")
        loader = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java"
        ).read_text(encoding="utf-8")
        service = (
            ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
            "fnaudio" / "client" / "playback" / "PlaybackService.java"
        ).read_text(encoding="utf-8")
        self.assertIn("MAX_ARTWORK_PIXELS = 4L * 1024L * 1024L", decoder)
        self.assertIn("bounds.inJustDecodeBounds = true", decoder)
        self.assertIn("(long) bounds.outWidth * (long) bounds.outHeight > MAX_ARTWORK_PIXELS", decoder)
        self.assertIn("ArtworkBitmapDecoder.decode(data)", loader)
        self.assertIn("ArtworkBitmapDecoder.decode(artworkData)", service)

    def test_stale_tpps_worker_cannot_stop_a_newer_native_session(self):
        source = TPPS_TUNNEL.read_text(encoding="utf-8")
        self.assertIn("if (isCurrent(requestGeneration)) {\n                stopNativeSession();", source)
        self.assertGreaterEqual(source.count("if (isCurrent(requestGeneration)) {"), 2)

    def test_restore_advances_engine_epoch_to_isolate_delayed_events(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn('EXTRA_ENGINE_EPOCH, nextCounter(persistedLong(snapshot, "engine_epoch", 0L))', source)
        self.assertIn("private static long nextCounter(long value)", source)

    def test_session_identity_rejects_malformed_present_counters(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("Long generation = optionalCounter(data, \"generation\")", source)
        self.assertIn('data.has("generation") && generation == null', source)
        self.assertIn("private static Long optionalCounter(JSONObject data, String key)", source)

    def test_queued_state_updates_recheck_session_identity_on_main_thread(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("final long eventGeneration = remoteSessionGeneration", source)
        self.assertGreaterEqual(source.count("remoteSessionStillCurrent(eventGeneration, eventEngineEpoch)"), 2)
        self.assertIn("private boolean remoteSessionStillCurrent(long generation, long engineEpoch)", source)

    def test_non_legacy_sessions_require_identity_fields_on_inbound_events(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn('remoteSessionGeneration > 0L && !data.has("generation")', source)
        self.assertIn('remoteEngineEpoch > 0L && !data.has("engine_epoch")', source)

    def test_state_version_is_committed_only_after_main_thread_identity_check(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        post = source.index("mainHandler.post(() -> {")
        version_check = source.index("remoteLastStateVersion > 0L && stateVersion < remoteLastStateVersion")
        self.assertGreater(version_check, post)

    def test_remote_status_does_not_allow_zero_version_to_regress_confirmed_state(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("remoteLastStateVersion > 0L && stateVersion < remoteLastStateVersion", source)

    def test_identity_numbers_must_be_integral(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("numeric != Math.rint(numeric)", source)
        self.assertIn("(data.has(\"generation\") && generation == null)", source)

    def test_cancelled_remote_requests_are_not_logged_as_network_failures(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("call.isCanceled()"), 2)
        self.assertIn("remote_event_stream ended: cancelled", source)

    def test_remote_sse_line_reader_does_not_discard_a_coalesced_read_tail(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        reader = source[source.index("private static String readBoundedLine("):source.index("private void onRemoteEventStreamEnded", source.index("private static String readBoundedLine("))]
        self.assertIn("reader.read(character, 0, 1)", reader)
        self.assertNotIn("reader.read(buffer)", reader)
        self.assertIn("if (count == 0) continue;", reader)

    def test_restore_reports_activation_rejection_instead_of_false_ready(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("private boolean enableRemoteMode(Intent intent)", source)
        self.assertIn("remote_session_restore failed: activation_rejected", source)

    def test_remote_stop_command_is_deduplicated_until_confirmation(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "RemotePlaybackPlayer.java").read_text(encoding="utf-8")
        self.assertIn("private boolean pendingStop", source)
        self.assertIn("if (pendingStop) return Futures.immediateVoidFuture();", source)
        self.assertIn('else if ("stop".equals(action) && pendingStopToken == requestToken) pendingStop = false;', source)
        self.assertIn("private long pendingStopToken", source)
        self.assertNotIn("if (!playing) pendingStop = false;", source)
        service = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        confirmed = service[service.index("if (success && applied) {"):service.index("} else if (success)")]
        self.assertIn('if ("stop".equals(action))', confirmed)
        self.assertIn("clearPendingCommandIfCurrent(", confirmed)

    def test_remote_media_item_seek_loads_the_requested_queue_item(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "RemotePlaybackPlayer.java").read_text(encoding="utf-8")
        self.assertIn('commandHandler.onRemoteCommand("load", Math.max(0L, positionMs), playlist.get(nextIndex).mediaId, pendingSeekToken);', source)
        self.assertIn("pendingSeekIndex", source)
        self.assertIn("pendingSeekPositionMs", source)
        self.assertIn("pendingSeekToken", source)
        self.assertIn("targetPositionReached", source)
        self.assertIn('else if ("seek".equals(action) || "load".equals(action))', source)
        self.assertNotIn('String action = nextIndex > currentIndex ? "next" : "previous";', source)

    def test_destroyed_playback_service_rejects_late_remote_command_results(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("private boolean remoteCommandStillCurrent(String targetId, long generation, long engineEpoch)", source)
        self.assertIn("return !destroyed && targetId != null && targetId.equals(remoteTargetId)", source)

    def test_rejected_remote_command_clears_its_pending_ticket(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        unavailable = source[source.index('remote_command rejected: session_unavailable'):source.index('final String commandTargetId')]
        self.assertIn("clearPendingCommandIfCurrent(", unavailable)
        payload = source[source.index('} catch (Exception ignored) {', source.index('final String commandTargetId')):source.index('Request request = authenticatedRequest')]
        self.assertIn("clearPendingCommandIfCurrent(", payload)

    def test_native_queue_rejects_non_http_media_and_bounds_metadata(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "web" / "NativePlaybackBridge.java").read_text(encoding="utf-8")
        self.assertIn("private static boolean isHttpUri(String value)", source)
        self.assertIn("!isHttpUri(uri)", source)
        self.assertIn("MAX_MEDIA_TEXT_LENGTH", source)
        self.assertIn("Math.min(MAX_TIME_MS, durationMs)", source)
        self.assertIn("MAX_QUEUE_ITEMS = 500", source)
        self.assertIn("Math.min(array.length(), MAX_QUEUE_ITEMS)", source)
        self.assertIn("stringField(row, \"id\")", source)
        self.assertIn("private static long longField(JSONObject row, String key)", source)
        self.assertIn("numeric != Math.rint(numeric)", source)
        self.assertNotIn("row.optString(\"id\")", source)

    def test_media_authentication_is_scoped_per_network_request(self):
        service = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                   "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        factory = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                   "fnaudio" / "client" / "network" / "HttpClientFactory.java").read_text(encoding="utf-8")
        self.assertIn("HttpClientFactory.createMediaClient(this, profile)", service)
        self.assertNotIn("dataSourceFactory.setDefaultRequestProperties(headers)", service)
        self.assertIn("builder.addNetworkInterceptor", factory)
        self.assertIn("sameProfileOrigin(profile, request)", factory)
        self.assertIn('.removeHeader("Authorization")', factory)
        self.assertIn('.removeHeader("X-Fnaudio-Trim-Token")', factory)
        self.assertIn('.removeHeader("Cookie")', factory)

    def test_fallback_artwork_is_serialized_and_staged_before_replacement(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "web" / "NativePlaybackBridge.java").read_text(encoding="utf-8")
        method = source[source.index("private static Uri createFallbackArtworkUri"):source.index("private static int repeatMode")]
        self.assertIn("FALLBACK_ARTWORK_LOCK", source)
        self.assertIn("synchronized (FALLBACK_ARTWORK_LOCK)", method)
        self.assertIn("new File(file.getPath() + \".tmp.\" + UUID.randomUUID())", method)
        self.assertIn("temporary.renameTo(file)", method)
        self.assertNotIn("new FileOutputStream(file)", method)

    def test_fallback_artwork_validates_existing_files_and_handles_generation_failure(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "web" / "NativePlaybackBridge.java").read_text(encoding="utf-8")
        method = source[source.index("private static Uri createFallbackArtworkUri"):source.index("private static int repeatMode")]
        self.assertIn("if (!isUsableFallbackArtwork(file))", method)
        self.assertIn("BitmapFactory.Options options", method)
        self.assertIn("options.inJustDecodeBounds = true", method)
        self.assertIn("options.outWidth == 512 && options.outHeight == 512", method)
        self.assertIn("MAX_FALLBACK_ARTWORK_BYTES", source)
        self.assertIn("catch (OutOfMemoryError | IOException | RuntimeException ignored)", method)

    def test_profile_and_relay_config_use_strict_json_field_types(self):
        profile = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "data" / "ConnectionProfile.java").read_text(encoding="utf-8")
        relay = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectRelayConfigClient.java").read_text(encoding="utf-8")
        self.assertIn("private static String stringField(JSONObject object, String key)", profile)
        self.assertIn("private static int intField(JSONObject object, String key, int fallback)", profile)
        self.assertIn("numeric != Math.rint(numeric)", profile)
        self.assertIn("private static String stringField(JSONObject object, String key)", relay)
        self.assertIn("private static int intField(JSONObject object, String key, int fallback)", relay)
        self.assertNotIn('server.optInt("port", 0)', relay)
        self.assertNotIn('server.optString("ip")', relay)

    def test_auth_status_and_profile_booleans_do_not_coerce_json_values(self):
        auth = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnOsAuthClient.java").read_text(encoding="utf-8")
        profile = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "data" / "ConnectionProfile.java").read_text(encoding="utf-8")
        self.assertIn("booleanField(payload, \"success\")", auth)
        self.assertIn("intField(payload, \"code\", -1)", auth)
        self.assertNotIn('payload.optInt("code", -1)', auth)
        self.assertIn("booleanField(json, \"https\", false)", profile)
        self.assertIn("booleanField(json, \"fnConnectRelay\", false)", profile)

    def test_persisted_remote_session_fields_are_type_checked(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn('persistedInt(snapshot, "schema", 0)', source)
        self.assertIn('persistedLong(snapshot, "saved_at_ms", 0L)', source)
        self.assertIn('persistedBoolean(snapshot, "playing", false)', source)
        self.assertIn("private static long persistedLong(JSONObject object, String key, long fallback)", source)
        self.assertNotIn('snapshot.optInt("schema", 0)', source)

    def test_remote_session_target_identity_is_bounded_at_service_entry(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("MAX_REMOTE_TARGET_ID_CHARS = 256", source)
        self.assertIn("MAX_REMOTE_TARGET_NAME_CHARS = 512", source)
        self.assertIn("boundedIdentity(safeStringExtra(intent, EXTRA_TARGET_ID), MAX_REMOTE_TARGET_ID_CHARS)", source)
        self.assertIn('boundedIdentity(persistedString(snapshot, "target_id", ""), MAX_REMOTE_TARGET_ID_CHARS)', source)
        self.assertIn("private static String boundedIdentity(@Nullable String value, int maxChars)", source)

    def test_fn_connect_resolver_does_not_coerce_hosts_or_ports(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        self.assertIn("Object item = ((JSONArray) value).opt(i);", source)
        self.assertIn("if (!(item instanceof String)) continue;", source)
        self.assertIn("private static int intField(JSONObject object, String key, int fallback)", source)
        self.assertNotIn("((JSONArray) value).optString(i)", source)
        self.assertNotIn('object.optInt(first, object.optInt(second, fallback))', source)

    def test_remote_playback_state_rejects_coerced_position_and_identity_fields(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn('secondsField(position, "rel_seconds", 0L)', source)
        self.assertIn('secondsField(core, "position", 0L)', source)
        self.assertIn('booleanField(core, "playing", false)', source)
        self.assertIn('stringField(core, "current")', source)
        self.assertNotIn('core.optDouble("position", 0d)', source)

    def test_remote_service_reuses_fn_connect_web_session_cookie(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        start = source.index("private Request.Builder authenticatedRequest")
        end = source.index("private List<MediaItem> parseRemoteItems", start)
        block = source[start:end]
        self.assertIn("import android.webkit.CookieManager;", source)
        self.assertIn("else if (profile != null && profile.webSession)", block)
        self.assertIn("CookieManager.getInstance().getCookie(url)", block)
        self.assertIn('request.header("Cookie", cookie)', block)

        loader = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "playback" / "AuthenticatedBitmapLoader.java").read_text(encoding="utf-8")
        self.assertIn("import android.webkit.CookieManager;", loader)
        self.assertIn("!profile.webSession && !profile.token.isEmpty()", loader)
        self.assertIn("CookieManager.getInstance().getCookie(uri.toString())", loader)
        self.assertIn("(!profile.webSession && profile.token.isEmpty())", loader)

    def test_remaining_android_json_boundaries_reject_object_string_coercion(self):
        tpps = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "TppsTunnel.java").read_text(encoding="utf-8")
        store = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "data" / "SecureProfileStore.java").read_text(encoding="utf-8")
        service = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        activity = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn('stringField(config, "visit_server")', tpps)
        self.assertIn('booleanField(applied, "ok", false)', tpps)
        self.assertIn('stringField(state, "activeId")', store)
        self.assertIn('stringField(data, "command_id")', service)
        self.assertIn('stringField(core, "command_ticket")', service)

    def test_controller_reconnect_releases_old_session_before_new_connection(self):
        activity = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                    "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        reconnect = activity[activity.index("private void connectMediaController()"):activity.index("private void injectNativeEnvironment()")]
        self.assertIn("pendingControllerCommands.clear();", reconnect)
        self.assertIn("MediaController.releaseFuture(controllerFuture);", reconnect)
        self.assertIn("mediaController.release();", reconnect)
        self.assertLess(reconnect.index("mediaController.release();"), reconnect.index("new MediaController.Builder"))

    def test_native_http_response_headers_are_bounded_and_filtered(self):
        activity = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                    "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("MAX_NATIVE_HTTP_RESPONSE_HEADER_COUNT", activity)
        self.assertIn("MAX_NATIVE_HTTP_RESPONSE_HEADERS_BYTES", activity)
        self.assertIn("MAX_NATIVE_HTTP_RESPONSE_HEADER_VALUE_CHARS", activity)
        self.assertIn('lower.equals("authorization")', activity)
        self.assertIn("responseHeaders(closeable.headers())", activity)
        self.assertIn("if (!(rawValue instanceof String)) throw new IllegalArgumentException", activity)
        self.assertNotIn('headers.optString(name, "")', activity)

    def test_relay_config_bounds_individual_native_config_fields(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectRelayConfigClient.java").read_text(encoding="utf-8")
        self.assertIn("MAX_TOKEN_CHARS = 4096", source)
        self.assertIn("MAX_SECRET_CHARS = 4096", source)
        self.assertIn("MAX_HOST_CHARS = 255", source)
        self.assertIn("MAX_STUN_CHARS = 512", source)
        self.assertIn("token.length() > MAX_TOKEN_CHARS", source)
        self.assertIn("protocol.length() > MAX_PROTOCOL_CHARS", source)

    def test_relay_config_rejects_unsafe_native_server_host_syntax(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectRelayConfigClient.java").read_text(encoding="utf-8")
        validation = source[source.index("if (token.isEmpty()"):source.index("JSONObject result", source.index("if (token.isEmpty()"))]
        helper = source[source.index("private static boolean safeHost"):source.index("private static int intField", source.index("private static boolean safeHost"))]
        self.assertIn("!safeHost(host)", validation)
        self.assertIn("character != '.'", helper)
        self.assertIn("character != '-'", helper)
        self.assertIn("character != ':'", helper)
        self.assertNotIn("Character.isWhitespace", helper)

    def test_fnos_auth_bounds_websocket_json_and_extracted_text(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnOsAuthClient.java").read_text(encoding="utf-8")
        self.assertIn("MAX_AUTH_MESSAGE_CHARS = 256 * 1024", source)
        self.assertIn("MAX_AUTH_VALUE_CHARS = 16 * 1024", source)
        self.assertIn("text == null || text.length() > MAX_AUTH_MESSAGE_CHARS", source)
        self.assertIn("text.length() <= MAX_AUTH_VALUE_CHARS", source)

    def test_fn_connect_resolver_bounds_published_host_candidates(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        self.assertIn("MAX_HOSTS_PER_FAMILY = 64", source)
        self.assertIn("MAX_HOST_CHARS = 255", source)
        self.assertIn("hosts.size() >= MAX_HOSTS_PER_FAMILY", source)
        self.assertIn("host.length() <= MAX_HOST_CHARS", source)

    def test_fn_connect_direct_fallback_reads_nested_network_addresses(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnConnectResolver.java").read_text(encoding="utf-8")
        fallback = source[source.index("private ConnectionProfile fallback("):source.index("private ConnectionProfile firstPublished(")]
        self.assertIn('JSONObject network = data.optJSONObject("network");', fallback)
        self.assertIn('collect(ipv6Hosts, network, "publicIpv6", "publicIPv6", "ipv6", "public_ipv6");', fallback)
        self.assertIn('collect(ipv4Hosts, network, "publicIpv4", "publicIPv4", "publicIp", "publicIP", "ipv4", "public_ipv4");', fallback)

    def test_android_json_scan_has_no_implicit_opt_string_reads(self):
        java_files = list((ROOT / "android-client" / "app" / "src" / "main" / "java").rglob("*.java"))
        remaining = []
        for path in java_files:
            text = path.read_text(encoding="utf-8")
            if "optString(" in text or "optInt(" in text or "optLong(" in text or "optDouble(" in text or "optBoolean(" in text:
                remaining.append(path.name)
        self.assertEqual([], remaining)

    def test_remote_queue_bounds_items_metadata_duration_and_artwork_scheme(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("MAX_REMOTE_QUEUE_ITEMS", source)
        self.assertIn("Math.min(array.length(), MAX_REMOTE_QUEUE_ITEMS)", source)
        self.assertIn("MAX_REMOTE_QUEUE_JSON_CHARS", source)
        self.assertIn("stringField(row, \"id\")", source)
        self.assertIn("MAX_REMOTE_METADATA_CHARS", source)
        self.assertIn("MAX_REMOTE_DURATION_MS", source)
        self.assertIn("safeRemoteArtworkUri", source)
        self.assertIn("numeric != Math.rint(numeric)", source)
        self.assertIn("Double.isFinite(numeric)", source)
        self.assertIn('"http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)', source)
        self.assertIn("uri.getHost() != null", source)
        self.assertIn("uri.getUserInfo() == null", source)
        self.assertIn("port >= 1 && port <= 65535", source)

    def test_main_activity_bounds_commands_waiting_for_media_controller(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("MAX_PENDING_CONTROLLER_COMMANDS", source)
        self.assertIn("pendingControllerCommands.size() >= MAX_PENDING_CONTROLLER_COMMANDS", source)
        self.assertIn("pendingControllerCommands.removeFirst()", source)

    def test_main_activity_releases_connected_media_controller_on_destroy(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        start = source.index("protected void onDestroy()")
        end = source.index("super.onDestroy()", start)
        block = source[start:end]
        self.assertIn("MediaController.releaseFuture(controllerFuture)", block)
        self.assertIn("mediaController.release()", block)

    def test_native_playback_commands_do_not_create_an_unbounded_outer_main_queue(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "web" / "NativePlaybackBridge.java").read_text(encoding="utf-8")
        self.assertIn("provider.dispatchWhenReady", source)
        self.assertNotIn("mainHandler.post", source)

    def test_https_webview_disallows_mixed_content(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("WebSettings.MIXED_CONTENT_NEVER_ALLOW", source)
        self.assertNotIn("WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE", source)

    def test_webview_self_signed_certificate_override_is_scoped_to_the_profile_origin(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        start = source.index("public void onReceivedSslError")
        end = source.index("        });", start)
        block = source[start:end]
        self.assertIn("sameProfileOrigin(profile, errorUri)", block)
        self.assertNotIn("profile.host.equalsIgnoreCase(Uri.parse(error.getUrl()).getHost())", block)

    def test_command_core_confirmation_applies_playing_state(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn('core.has("playing")', source)
        self.assertIn("remotePlayer.updateStatus(index, positionMs, durationMs, playing)", source)

    def test_fn_connect_accepts_only_https_for_allowed_hosts(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "FnConnectActivity.java").read_text(encoding="utf-8")
        self.assertIn('!"https".equalsIgnoreCase(uri.getScheme())', source)
        self.assertIn("isAllowedFnConnectUri(uri)", source)
        self.assertIn("shouldOverrideUrlLoading(WebView view, WebResourceRequest request)", source)
        self.assertIn("request == null || !isAllowedFnConnectUri(request.getUrl())", source)

    def test_main_activity_never_treats_another_scheme_or_default_port_as_same_server(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("return sameProfileOrigin(profile, uri);", source)
        self.assertIn("int actualPort = uri.getPort() < 0 ? 443 : uri.getPort();", source)
        self.assertIn("int actualPort = uri.getPort() < 0 ? defaultPort : uri.getPort();", source)

    def test_main_activity_does_not_forward_a_page_supplied_cgi_route_header(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        intercept_start = source.index("private WebResourceResponse interceptAuthenticatedGet")
        bridge_start = source.index("public void requestJson", intercept_start)
        bridge_end = source.index("public void rejectRequestJson", bridge_start)
        intercept = source[intercept_start:bridge_start]
        bridge = source[bridge_start:bridge_end]
        self.assertIn('lower.equals("x-fnaudio-path")', intercept)
        self.assertIn('lower.equals("x-fnaudio-path")', bridge)

    def test_remote_player_keeps_pending_mode_requests_across_stale_server_snapshots(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "playback" / "RemotePlaybackPlayer.java").read_text(encoding="utf-8")
        start = source.index("public void updateModes")
        end = source.index("public void clearPendingCommand", start)
        block = source[start:end]
        self.assertIn("if (pendingRepeatMode == null) requestedRepeatMode = this.repeatMode;", block)
        self.assertIn("if (pendingShuffle == null) requestedShuffle = shuffle;", block)
        self.assertNotIn("this.requestedRepeatMode = this.repeatMode;", block)
        self.assertNotIn("this.requestedShuffle = shuffle;", block)

    def test_remote_player_stop_cancels_pending_seek_projection(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "playback" / "RemotePlaybackPlayer.java").read_text(encoding="utf-8")
        start = source.index("protected ListenableFuture<?> handleStop()")
        end = source.index("protected ListenableFuture<?> handleSeek", start)
        block = source[start:end]
        self.assertIn("pendingSeekIndex = null;", block)
        self.assertIn("pendingSeekPositionMs = null;", block)

    def test_playback_service_type_checks_intent_extras(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        self.assertIn("private static int safeIntExtra", source)
        self.assertIn("private static long safeLongExtra", source)
        self.assertIn("private static boolean safeBooleanExtra", source)
        self.assertIn("private static String safeStringExtra", source)
        self.assertNotIn("intent.getIntExtra(EXTRA_INDEX", source)
        self.assertNotIn("intent.getLongExtra(EXTRA_POSITION_MS", source)
        self.assertNotIn("intent.getStringExtra(EXTRA_QUEUE_JSON", source)
        self.assertNotIn("intent.getStringExtra(EXTRA_TARGET_ID", source)

    def test_exported_android_entrypoints_type_check_intent_extras(self):
        main = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")
        login = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                 "fnaudio" / "client" / "ui" / "LoginActivity.java").read_text(encoding="utf-8")
        fnconnect = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                     "fnaudio" / "client" / "ui" / "FnConnectActivity.java").read_text(encoding="utf-8")
        self.assertIn("safeStringExtra(getIntent(), EXTRA_PROFILE_ID)", main)
        self.assertIn("safeBooleanExtra(getIntent(), EXTRA_SKIP_AUTO_RESUME, false)", login)
        self.assertIn("safeStringExtra(data, ConnectionHistoryActivity.EXTRA_PROFILE_ID)", login)
        self.assertIn("safeStringExtra(getIntent(), EXTRA_FN_ID)", fnconnect)

    def test_present_malformed_session_counter_is_not_downgraded_to_zero(self):
        source = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" /
                  "fnaudio" / "client" / "playback" / "PlaybackService.java").read_text(encoding="utf-8")
        start = source.index("private static Long intentCounter")
        end = source.index("private static int safeIntExtra", start)
        block = source[start:end]
        self.assertIn("intent.getExtras()", block)
        self.assertIn("if (!(raw instanceof Long)) return null;", block)
        self.assertIn("value < 0L ? null", block)
        self.assertNotIn("boundedCounter(safeLongExtra(intent, key, -1L))", block)


if __name__ == "__main__":
    unittest.main()
