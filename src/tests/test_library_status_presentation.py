import sys
import unittest

sys.path.insert(0, "app/server")

from library_status_presentation import status_message


class LibraryStatusPresentationTests(unittest.TestCase):
    def test_invalid_path_messages_have_stable_priority(self):
        self.assertEqual(status_message({"allowed": False, "exists": True}), "出于安全保护，这个路径不能作为音乐目录")
        self.assertEqual(status_message({"allowed": True, "exists": False}), "音乐目录不存在，请在应用设置里选择正确的音乐文件夹")
        self.assertEqual(status_message({"allowed": True, "exists": True, "is_dir": False}), "音乐路径不是文件夹")
        self.assertEqual(status_message({"allowed": True, "exists": True, "is_dir": True, "readable": False}), "应用没有权限读取这个音乐文件夹")

    def test_scan_and_ready_messages_use_count(self):
        base = {"allowed": True, "exists": True, "is_dir": True, "readable": True}
        self.assertEqual(status_message({**base, "scanning": True, "count": 0}), "正在扫描音乐目录")
        self.assertEqual(status_message({**base, "scanning": True, "count": 2}), "音乐库已就绪")
        self.assertEqual(status_message({**base, "scanning": False, "count": 0}), "没有在这个目录里找到支持的音乐文件")
