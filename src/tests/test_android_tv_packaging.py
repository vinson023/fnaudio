"""Guard the standalone television packages.

The repository ships one APK with two entry points, but a vendor launcher that
ignores ``LEANBACK_LAUNCHER`` opens the phone client on a television. The TV
build types therefore drop the phone entry and ship one ABI each, and three
things must stay true or the artefact silently regresses:

* the three build types keep the same manifest fragment -- a divergent copy is
  how one of the two ABIs ships a touch-only launcher;
* the phone entry is actually removed and the television login actually carries
  ``LAUNCHER``, which is the whole point of the split;
* the 32-bit package carries a real 32-bit ``libgojni.so``, not a renamed
  arm64 build, and its JNI surface still matches the 64-bit one.

The manifest copies exist because AGP only creates a build type's source set
after ``buildTypes`` is declared, so ``manifest.srcFile`` cannot point three
build types at one file. Byte equality is the contract that replaces it.
"""

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
ANDROID_ROOT = REPO_ROOT / "android-client"
APP_ROOT = ANDROID_ROOT / "app"
BUILD_GRADLE = APP_ROOT / "build.gradle"
TV_BUILD_TYPES = ("tvArm64", "tvArm32", "tvEmulator")
TV_BUILD_SCRIPT = REPO_ROOT / "tools" / "build_tv_apk.ps1"

EM_ARM = 40
EM_AARCH64 = 183

JNI_SYMBOL = re.compile(rb"Java_[A-Za-z0-9_]{3,80}")


def manifest_for(build_type):
    return APP_ROOT / "src" / build_type / "AndroidManifest.xml"


def elf_machine(path):
    header = path.read_bytes()[:20]
    if header[:4] != b"\x7fELF":
        raise AssertionError("%s is not an ELF shared object" % path)
    return int.from_bytes(header[18:20], "little")


class AndroidTvPackagingTests(unittest.TestCase):
    def test_every_tv_build_type_ships_the_same_manifest(self):
        reference = manifest_for("tvArm64").read_bytes()
        for build_type in TV_BUILD_TYPES[1:]:
            self.assertEqual(
                reference,
                manifest_for(build_type).read_bytes(),
                "%s must carry byte-identical television manifest" % build_type,
            )

    def test_phone_launcher_is_removed_and_television_launcher_added(self):
        text = manifest_for("tvArm64").read_text(encoding="utf-8")
        main_text = (APP_ROOT / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        # The combined package keeps both entry points; the TV fragment must not
        # touch the Leanback one, only add the plain launcher the vendor shells
        # actually enumerate.
        self.assertIn("android.intent.category.LEANBACK_LAUNCHER", main_text)
        self.assertIn("android.intent.category.LAUNCHER", main_text)
        remove_at = text.index('tools:node="remove"')
        self.assertLess(text.index(".ui.LoginActivity"), remove_at)
        self.assertLess(remove_at, text.index(".tv.TvLoginActivity"))
        self.assertIn("android.intent.category.LAUNCHER", text[text.index(".tv.TvLoginActivity"):])

    def test_build_types_pin_one_abi_each(self):
        gradle = BUILD_GRADLE.read_text(encoding="utf-8")
        self.assertIn('abiFilters "arm64-v8a"', gradle)
        self.assertIn('abiFilters "armeabi-v7a"', gradle)
        self.assertIn("applicationIdSuffix \".tv\"", gradle)
        self.assertIn("versionNameSuffix \"-tv\"", gradle)

    def test_arm32_native_library_is_really_32_bit_and_matches_arm64(self):
        arm32 = APP_ROOT / "src" / "tvArm32" / "jniLibs" / "armeabi-v7a" / "libgojni.so"
        arm64 = APP_ROOT / "src" / "main" / "jniLibs" / "arm64-v8a" / "libgojni.so"
        self.assertTrue(arm32.is_file(), "the 32-bit TV build needs its own libgojni.so")
        self.assertEqual(EM_ARM, elf_machine(arm32))
        self.assertEqual(EM_AARCH64, elf_machine(arm64))
        # Same gomobile binding means the same exported Java_* names. A library
        # rebuilt from a different Go surface would load and then fail at the
        # first call, which is much harder to diagnose than a failing build.
        arm32_symbols = set(JNI_SYMBOL.findall(arm32.read_bytes()))
        arm64_symbols = set(JNI_SYMBOL.findall(arm64.read_bytes()))
        self.assertTrue(arm64_symbols, "arm64 libgojni.so exposes no JNI symbols")
        self.assertEqual(arm64_symbols, arm32_symbols)

    def test_tv_build_script_verifies_the_launcher_and_the_abi(self):
        script = TV_BUILD_SCRIPT.read_text(encoding="utf-8")
        for expected in (
            ":app:assembleTvArm64",
            ":app:assembleTvArm32",
            "TV_ANDROID_SHA256SUMS",
            "launchable-activity: name='com\\.fnaudio\\.client\\.tv\\.TvLoginActivity'",
            "com\\.fnaudio\\.client\\.ui\\.LoginActivity",
            "native-code: '$($variant.Abi)'",
            "arm64-v8a",
            "armeabi-v7a",
        ):
            self.assertIn(expected, script)

    def test_tv_client_exposes_search_favorites_and_playlists(self):
        api = (ANDROID_ROOT / "app" / "src" / "main" / "java" / "com" / "fnaudio" /
               "client" / "tv" / "TvApi.java").read_text(encoding="utf-8")
        for method in ("searchTracks(", "userState(", "tracksByIds(",
                       "groupsByView(", "creatorTracks(", "tracksByView("):
            self.assertIn(method, api)
        main = (ANDROID_ROOT / "app" / "src" / "main" / "java" / "com" / "fnaudio" /
                "client" / "tv" / "TvMainActivity.java").read_text(encoding="utf-8")
        for label in ('"收藏"', '"播放列表"', '"搜索"', '"设置"'):
            self.assertIn(label, main)


if __name__ == "__main__":
    unittest.main()
