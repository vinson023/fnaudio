"""D1 落地后的许可证文件契约：`LICENSE` 必须是逐字未改的 GPL-3.0 正文，
并且 `NOTICE`、`AUTHORS`、`README.md` 三处声明要与它互相咬合。

判别性：改写 `LICENSE` 的任意一个字节、把 `NOTICE` 里的摘要换成旧值、或把
README 的许可证段落改回「尚未明确」，本文件都会红。`LICENSE` 位于仓库根目录，
不在 `SOURCE_MANIFEST.sha256` 的覆盖面内（清单只遍历 `src/` 与 `android-client/`），
所以这里的摘要常量是磁盘上唯一能证明正文未被替换的机器可校验证据。
"""

import hashlib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
# gnu.org 发布的 GPL-3.0 逐字正文：35149 字节、LF 行尾、无行尾空白。
GPL3_VERBATIM_SHA256 = "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"
HOLDER = "vinson023"


class LicenseFileTests(unittest.TestCase):
    def setUp(self):
        self.license_bytes = (REPO_ROOT / "LICENSE").read_bytes()
        self.license = self.license_bytes.decode("utf-8")
        self.notice = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")
        self.authors = (REPO_ROOT / "AUTHORS").read_text(encoding="utf-8")
        self.readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    def test_license_text_is_verbatim_gpl3(self):
        digest = hashlib.sha256(self.license_bytes).hexdigest()
        self.assertEqual(
            digest,
            GPL3_VERBATIM_SHA256,
            "LICENSE 必须是 gnu.org 的 GPL-3.0 逐字正文，不得改写、翻译或裁剪",
        )
        self.assertEqual(len(self.license_bytes), 35149, "正文长度与逐字摘要必须同时吻合")
        self.assertIn("                    GNU GENERAL PUBLIC LICENSE", self.license.splitlines()[0])
        self.assertIn("Version 3, 29 June 2007", self.license)
        self.assertNotIn("\r", self.license, "根目录文本文件按 .gitattributes 统一为 LF")

    def test_notice_binds_holder_version_and_digest(self):
        self.assertIn(f"Copyright (C) 2026 {HOLDER}", self.notice)
        self.assertIn("GPL-3.0-or-later", self.notice)
        self.assertIn(
            GPL3_VERBATIM_SHA256,
            self.notice,
            "NOTICE 记录的正文摘要要与磁盘上的 LICENSE 一致",
        )
        # 再分发义务是这次裁定要写清的一条，不能只留一句「详见 LICENSE」。
        self.assertIn("FPK", self.notice)
        self.assertIn("APK", self.notice)
        self.assertIn("对应源码", self.notice)

    def test_authors_names_only_the_confirmed_holder(self):
        self.assertIn(HOLDER, self.authors)
        self.assertIn("版权持有人", self.authors)
        # 负责人只给了一个署名对象，没有给联系方式：AUTHORS 里不能出现
        # 任何未经确认的邮箱或占位署名，否则就是把猜测写成了事实。
        self.assertNotIn("@", self.authors, "AUTHORS 不得出现未确认的邮箱地址")
        for placeholder in ("待定", "TBD", "占位", "TODO:"):
            self.assertNotIn(placeholder, self.authors, "AUTHORS 不得保留占位署名")

    def test_readme_states_the_licence_and_its_files(self):
        self.assertNotIn("许可证尚未明确", self.readme, "D1 已裁定，README 不能再停在「尚未明确」")
        self.assertIn("GPL-3.0-or-later", self.readme)
        for name in ("LICENSE", "AUTHORS", "NOTICE"):
            self.assertIn(f"`{name}`", self.readme)

    def test_repository_is_still_unhosted(self):
        # 裁定是「开源，暂不托管」：托管状态由 remote 列表证明，而不是由文档声明证明。
        remotes = (REPO_ROOT / ".git" / "config").read_text(encoding="utf-8")
        self.assertNotIn("[remote ", remotes, "暂不托管：.git/config 里不应出现 remote 段")


if __name__ == "__main__":
    unittest.main()