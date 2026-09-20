import math
import unittest

from app.server.metadata_job_payload_policy import MAX_JOB_TEXT, project_metadata_job_payload


class MetadataJobPayloadPolicyTests(unittest.TestCase):
    def test_projects_only_provider_and_local_reader_fields(self):
        result = project_metadata_job_payload({
            "title": " Song ", "path": "/music/song.flac", "duration": 12.5,
            "size": 4, "modified_ns": 5, "item_json": "x" * 100000,
        })
        self.assertEqual(result["title"], "Song")
        self.assertEqual(result["duration"], 12.5)
        self.assertNotIn("item_json", result)

    def test_rejects_nonfinite_and_truncates_text_without_stringifying(self):
        class Explosive:
            def __str__(self):
                raise AssertionError("payload values must not stringify")

        result = project_metadata_job_payload({
            "title": "x" * (MAX_JOB_TEXT + 1), "duration": math.inf,
            "path": Explosive(), "is_dsd": "true",
        })
        self.assertEqual(len(result["title"]), MAX_JOB_TEXT)
        self.assertNotIn("duration", result)
        self.assertNotIn("path", result)
        self.assertNotIn("is_dsd", result)


if __name__ == "__main__":
    unittest.main()
