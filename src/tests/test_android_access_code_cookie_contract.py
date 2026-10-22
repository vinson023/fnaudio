from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "MainActivity.java").read_text(encoding="utf-8")


assert "private static String accessCodeCookie(ConnectionProfile requestProfile)" in SOURCE
assert "CookieManager.getInstance().getCookie(requestProfile.httpOrigin())" in SOURCE
assert "return access.isEmpty() ? combined : combined + \"; \" + access;" in SOURCE
assert "builder.header(\"Cookie\", authenticatedCookie(requestProfile, null));" in SOURCE
