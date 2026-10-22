from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
layout = (ROOT / "android-client/app/src/main/res/layout/activity_login.xml").read_text(encoding="utf-8")
source = (ROOT / "android-client/app/src/main/java/com/fnaudio/client/ui/LoginActivity.java").read_text(encoding="utf-8")
assert 'android:id="@+id/passwordVisibilityButton"' in layout
assert 'android:id="@+id/accessCodeVisibilityButton"' in layout
assert "toggleSecretVisibility(password, passwordVisibilityButton" in source
assert "toggleSecretVisibility(accessCode, accessCodeVisibilityButton" in source
assert "PasswordTransformationMethod.getInstance()" in source
assert "HideReturnsTransformationMethod.getInstance()" in source
