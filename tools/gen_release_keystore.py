"""生成 fnAudio 的 Android 正式发布 keystore，并把四项签名材料写进 .secrets/。

为什么单独一个脚本：
  Android 用签名证书判断「这是不是同一个应用」。已装的正式版认的是某一把密钥，
  keystore 一旦重生成，新 APK 就再也覆盖不上去，只能让用户卸载重装（本地数据全丢）。
  所以这里**拒绝覆盖已有文件**，只有显式 --force 才重建，重建前会先把旧的改名留存。

产出：
  .secrets/fnaudio-release.jks        keystore（PKCS12，RSA 4096，30 年）
  .secrets/release-signing.env        四项环境变量，供 tools/load_signing_env.ps1 读取

`.secrets/` 已在 .gitignore 里，不会进仓库，也不进 SOURCE_MANIFEST（清单只扫 src/ 与
android-client/）。备份要求见 docs/ANDROID_RELEASE.md：必须离线加密留一份，
丢了就永远发不出能覆盖升级的包。

用法：
  python tools/gen_release_keystore.py
  python tools/gen_release_keystore.py --force     # 仅在确认要作废旧身份时使用
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / ".secrets"
KEYSTORE = SECRETS / "fnaudio-release.jks"
ENV_FILE = SECRETS / "release-signing.env"
ALIAS = "fnaudio"
VALIDITY_DAYS = 10950  # 30 年，Android 要求长于应用可能的寿命
DNAME = "CN=fnAudio, OU=fnAudio, O=fnAudio, L=Shenzhen, ST=Guangdong, C=CN"


def find_keytool() -> Path:
    java = shutil.which("java")
    candidates: list[Path] = []
    if java:
        candidates.append(Path(java).resolve().parent / "keytool.exe")
        candidates.append(Path(java).resolve().parent / "keytool")
    for root in (Path("C:/Program Files/Java"), Path("C:/Program Files/Eclipse Adoptium")):
        if root.is_dir():
            for found in sorted(root.glob("*/bin/keytool.exe"), reverse=True):
                candidates.append(found)
    home = os.environ.get("JAVA_HOME")
    if home:
        candidates.append(Path(home) / "bin" / "keytool.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit("keytool 未找到；需要 JDK 17（C:/Program Files/Java/jdk-17/bin/keytool.exe）。")


def random_password(length: int = 32) -> str:
    # 只用字母数字：密码会经环境变量传进 Gradle 与 PowerShell，
    # 混入 $ ` " 之类字符时不同层要转义三次，出错点极难查。
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="作废现有签名身份并重建")
    args = parser.parse_args()

    if KEYSTORE.exists() and not args.force:
        print(f"已存在，拒绝覆盖：{KEYSTORE}")
        print("覆盖会让所有已安装的正式版无法升级。确需重建请加 --force。")
        return 1

    SECRETS.mkdir(parents=True, exist_ok=True)
    if KEYSTORE.exists():
        backup = KEYSTORE.with_suffix(".jks.retired")
        shutil.move(KEYSTORE, backup)
        print("旧 keystore 已改名留存：", backup)

    password = random_password()
    keytool = find_keytool()
    command = [
        str(keytool),
        "-genkeypair",
        "-keystore", str(KEYSTORE),
        "-storetype", "PKCS12",
        "-alias", ALIAS,
        "-keyalg", "RSA",
        "-keysize", "4096",
        "-validity", str(VALIDITY_DAYS),
        "-dname", DNAME,
        "-storepass", password,
        "-keypass", password,
        "-noprompt",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        return completed.returncode

    env_text = "\n".join(
        [
            "# fnAudio Android 正式签名材料。此文件已被 .gitignore 排除，禁止入库。",
            "# 用法：powershell -File tools/load_signing_env.ps1  然后跑 build_android_release.ps1",
            "# 丢失 keystore 等于永久失去正式版的覆盖升级能力，必须离线加密备份一份。",
            f"FNAUDIO_RELEASE_STORE_FILE={KEYSTORE}",
            f"FNAUDIO_RELEASE_STORE_PASSWORD={password}",
            f"FNAUDIO_RELEASE_KEY_ALIAS={ALIAS}",
            f"FNAUDIO_RELEASE_KEY_PASSWORD={password}",
            "",
        ]
    )
    ENV_FILE.write_text(env_text, encoding="utf-8")

    fingerprint = subprocess.run(
        [
            str(keytool), "-list", "-v",
            "-keystore", str(KEYSTORE),
            "-storepass", password,
            "-alias", ALIAS,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    sha = ""
    for line in (fingerprint.stdout or "").splitlines():
        if "SHA256:" in line:
            sha = line.split("SHA256:", 1)[1].strip()
    print("keystore:", KEYSTORE)
    print("env file:", ENV_FILE)
    print("alias   :", ALIAS)
    print("SHA-256 :", sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
