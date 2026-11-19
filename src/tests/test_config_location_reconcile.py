"""fnOS 把安装回调和服务守护进程指向不同配置目录时，服务要能找回真正的配置。

5.141 从 0.2.166 升到 0.2.167 后曲库变空：回调把完整配置写进
`@appconf/fnaudio/config.json`，而 `cmd/main` 是以 `@appcenter/fnaudio/etc`
启动的，`persist_backend_port` 从空 payload 造出 22 字节的
`{"server_port": 53199}`，服务读到的就是它。这些用例跑的是真脚本。
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


def find_bash():
    candidate = shutil.which("bash")
    if not candidate and os.name == "nt":
        fallback = pathlib.Path("C:/Program Files/Git/bin/bash.exe")
        candidate = str(fallback) if fallback.is_file() else None
    return candidate


class ConfigLocationReconcileTests(unittest.TestCase):
    def run_main_status(self, target_payload, sibling_payload):
        bash = find_bash()
        if not bash:
            self.skipTest("bash is unavailable")
        with tempfile.TemporaryDirectory(prefix="fnaudio-config-location-") as directory:
            fixture = pathlib.Path(directory)
            apps = fixture / "apps"
            app_dir = apps / "@appcenter" / "fnaudio"
            etc = app_dir / "etc"
            etc.mkdir(parents=True)
            var = app_dir / "var"
            var.mkdir()
            config = etc / "config.json"
            if target_payload is not None:
                config.write_text(json.dumps(target_payload), encoding="utf8")
            if sibling_payload is not None:
                sibling = apps / "@appconf" / "fnaudio" / "config.json"
                sibling.parent.mkdir(parents=True, exist_ok=True)
                sibling.write_text(json.dumps(sibling_payload), encoding="utf8")

            source = (ROOT / "src" / "cmd" / "main").read_text(encoding="utf8")
            source = source.replace(
                'PYTHON_BIN="/var/apps/python312/target/bin/python3"',
                'PYTHON_BIN="' + pathlib.Path(sys.executable).as_posix() + '"',
            )
            env = dict(
                os.environ,
                TRIM_APPDEST=app_dir.as_posix(),
                TRIM_PKGETC=etc.as_posix(),
                TRIM_PKGVAR=var.as_posix(),
            )
            result = subprocess.run(
                [bash, "--noprofile", "--norc", "-s", "status"],
                input=source,
                env=env,
                text=True,
                encoding="utf8",
                errors="replace",
                capture_output=True,
                timeout=40,
            )
            saved = json.loads(config.read_text(encoding="utf8")) if config.exists() else None
            log = (var / "info.log").read_text(encoding="utf8") if (var / "info.log").exists() else ""
            return result, saved, log

    def test_a_stub_config_adopts_the_sibling_file_the_callbacks_wrote(self):
        # 22 字节的 stub 就是 persist_backend_port 从空 payload 造出来的形状。
        result, saved, log = self.run_main_status(
            {"server_port": 53199},
            {
                "library_path": "/vol1/1000/music",
                "library_paths": ["/vol1/1000/music", "/vol02/1000-1-9ed159d1/music"],
                "server_port": 53199,
                "renderer_name": "Living room",
                "metadata_enabled": False,
            },
        )
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertEqual(
            saved["library_paths"], ["/vol1/1000/music", "/vol02/1000-1-9ed159d1/music"]
        )
        self.assertEqual(saved["library_path"], "/vol1/1000/music\n/vol02/1000-1-9ed159d1/music")
        # 目标文件自己的端口优先，其余设置从被采纳的那份带过来。
        self.assertEqual(saved["server_port"], 53199)
        self.assertEqual(saved["renderer_name"], "Living room")
        self.assertIs(saved["metadata_enabled"], False)
        self.assertIn("adopted library configuration from", log)

    def test_a_real_config_is_never_replaced_by_a_stale_sibling(self):
        # 用户主动清空曲库后，配置里其余设置还在；不能因为曲库为空就被旧文件填回去。
        original = {
            "library_path": "",
            "library_paths": [],
            "server_port": 53199,
            "renderer_name": "Bedroom",
            "mpd_mixer_type": "hardware",
        }
        result, saved, log = self.run_main_status(
            original,
            {
                "library_path": "/vol1/1000/music",
                "library_paths": ["/vol1/1000/music"],
                "server_port": 53199,
                "renderer_name": "Living room",
            },
        )
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertEqual(saved, original)
        self.assertNotIn("adopted library configuration", log)

    def test_a_missing_config_is_not_filled_from_a_sibling_without_roots(self):
        result, saved, log = self.run_main_status(None, {"server_port": 53199})
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIsNone(saved)
        self.assertNotIn("adopted library configuration", log)


if __name__ == "__main__":
    unittest.main()
