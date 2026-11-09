import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "android-client/app/src/main/java/com/fnaudio/client/ui/LoginActivity.java").read_text(encoding="utf-8")

# 1. 同一个按钮两种语义：忙时取消，闲时登录。
assert 'loginButton.setText(value ? "取消登录" : "登录");' in source, \
    "setBusy must swap the login label to 取消登录 while a run is in flight"
assert "if (busy) cancelLogin();" in source and "else loginWithPassword();" in source, \
    "the click listener must branch on busy before starting a second attempt"


def method_body(name):
    match = re.search(r"private void %s\([^)]*\)\s*\{" % re.escape(name), source)
    assert match, "method %s not found" % name
    start = match.end()
    depth = 1
    index = start
    while depth:
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        index += 1
    return source[start:index - 1]


cancel = method_body("cancelLogin")

# 2. 取消必须真的断掉两条在途链路：FN Connect 解析与 fnOS 握手。
assert "authClient.cancel();" in cancel, "cancelLogin must abort the fnOS handshake"
assert "fnConnectResolver.cancel();" in cancel, "cancelLogin must abort FN Connect resolution"

# 3. 不能用 close()：FnConnectResolver.close() 会 shutdown 专用 dispatcher，
#    取消一次之后整个解析器都废了，下一次登录会静默失败。
assert ".close()" not in cancel, \
    "cancelLogin must not close the resolver - close() shuts its dispatcher for good"

# 4. 取消后必须回到可再次点击的状态，否则按钮变成一次性。
assert "setBusy(false," in cancel, "cancelLogin must clear the busy state"
assert "if (!busy) return;" in cancel, "cancelLogin must be a no-op when nothing is running"

# 5. 按钮在任何状态下都不该被禁用：地址填错时最长要等 30 秒超时，
#    禁用等于把人锁在页面上。
set_busy = method_body("setBusy")
assert "loginButton.setEnabled(true);" in set_busy, \
    "the login button must stay enabled while busy so it can be used to cancel"
assert "loginButton.setEnabled(!value)" not in set_busy, \
    "the button must no longer be disabled during a run"
