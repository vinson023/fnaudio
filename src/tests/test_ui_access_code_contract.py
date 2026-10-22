import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AndroidAccessCodeContractTests(unittest.TestCase):
    def test_android_login_exposes_and_persists_access_code(self):
        layout = (ROOT / ".." / "android-client" / "app" / "src" / "main" / "res" / "layout" / "activity_login.xml").read_text(encoding="utf-8")
        profile = (ROOT / ".." / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "data" / "ConnectionProfile.java").read_text(encoding="utf-8")
        login = (ROOT / ".." / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "LoginActivity.java").read_text(encoding="utf-8")
        factory = (ROOT / ".." / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "HttpClientFactory.java").read_text(encoding="utf-8")
        auth = (ROOT / ".." / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "network" / "FnOsAuthClient.java").read_text(encoding="utf-8")
        self.assertIn('android:id="@+id/accessCode"', layout)
        self.assertIn('accessCode', profile)
        self.assertIn('withAccessCode', profile)
        self.assertIn('accessCode', login)
        self.assertIn('X-Access-Code', factory)
        self.assertIn('X-Access-Code', auth)

    def test_fn_connect_login_carries_access_code_into_resolved_profile(self):
        login = (ROOT / ".." / "android-client" / "app" / "src" / "main" / "java" / "com" / "fnaudio" / "client" / "ui" / "LoginActivity.java").read_text(encoding="utf-8")
        fn_connect_block = login[login.index('ConnectionProfile profile = ConnectionProfile.create('):login.index('authenticate(profile, passwordValue', login.index('ConnectionProfile profile = ConnectionProfile.create('))]
        self.assertIn('.withAccessCode(accessCode.getText().toString())', fn_connect_block)
