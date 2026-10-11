"""Automated tests for mygit.py.

Run from the project folder:
    python -m unittest test_mygit -v

Each test works in its own temporary folder, so your real repositories are not touched.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MYGIT = str(Path(__file__).resolve().parent / "mygit.py")


def run(folder, *args):
    """Run mygit with the given arguments inside folder. Returns the printed text."""
    result = subprocess.run(
        [sys.executable, MYGIT, *args],
        cwd=folder, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    return result.stdout + result.stderr


def ref_value(folder, ref):
    return (Path(folder) / ".mygit" / ref).read_text(encoding="utf-8").strip()


def current_tip(folder):
    head = (Path(folder) / ".mygit" / "HEAD").read_text(encoding="utf-8").strip()
    return ref_value(folder, head.split(":", 1)[1].strip())


def file_text(folder, name):
    return (Path(folder) / name).read_text(encoding="utf-8").strip()


class MyGitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        run(self.dir, "init")

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, folder, filename, text, message):
        (Path(folder) / filename).write_text(text + "\n", encoding="utf-8")
        run(folder, "add", filename)
        run(folder, "commit", "-m", message)
        return current_tip(folder)

    def test_commit_and_log(self):
        c1 = self.commit(self.dir, "a.txt", "one", "c1")
        self.assertEqual(len(c1), 40)
        self.assertIn("c1", run(self.dir, "log"))

    def test_branch_and_fast_forward_merge(self):
        self.commit(self.dir, "a.txt", "one", "base")
        run(self.dir, "branch", "topic")
        run(self.dir, "checkout", "topic")
        topic_tip = self.commit(self.dir, "t.txt", "topic", "topic one")
        run(self.dir, "checkout", "main")
        self.assertFalse((self.dir / "t.txt").exists())
        run(self.dir, "merge", "topic")
        self.assertTrue((self.dir / "t.txt").exists())
        self.assertEqual(current_tip(self.dir), topic_tip)

    def test_hard_reset_restores_files(self):
        c1 = self.commit(self.dir, "a.txt", "one", "c1")
        self.commit(self.dir, "a.txt", "two", "c2")
        run(self.dir, "reset", "--hard", c1, "--yes")
        self.assertEqual(current_tip(self.dir), c1)
        self.assertEqual(file_text(self.dir, "a.txt"), "one")

    def test_rebase_feature_onto_main(self):
        self.commit(self.dir, "base.txt", "base", "base")
        run(self.dir, "branch", "feature")
        run(self.dir, "checkout", "feature")
        self.commit(self.dir, "f1.txt", "f1", "feature one")
        run(self.dir, "checkout", "main")
        self.commit(self.dir, "m.txt", "m", "main two")
        run(self.dir, "checkout", "feature")
        out = run(self.dir, "rebase", "main")
        self.assertIn("Successfully rebased", out)
        self.assertTrue((self.dir / "m.txt").exists())
        self.assertTrue((self.dir / "f1.txt").exists())

    def test_annotated_tag_points_to_commit(self):
        c1 = self.commit(self.dir, "a.txt", "one", "c1")
        run(self.dir, "tag", "-a", "v1", "-m", "release")
        self.assertIn(c1, run(self.dir, "tag-show", "v1"))

    def test_fsck_passes_and_gc_finds_nothing(self):
        self.commit(self.dir, "a.txt", "one", "c1")
        self.assertIn("Check passed", run(self.dir, "fsck"))
        self.assertIn("Nothing to clean up", run(self.dir, "gc"))

    def test_push_fetch_and_rejected_push(self):
        server = self.dir / "server"
        work = self.dir / "work"
        server.mkdir()
        work.mkdir()
        run(server, "init")
        run(work, "init")

        w1 = self.commit(work, "a.txt", "one", "w1")
        run(work, "remote", "add", "origin", str(server))
        run(work, "push", "origin")
        self.assertEqual(ref_value(server, "refs/heads/main"), w1)

        s1 = self.commit(server, "s.txt", "server", "server-only")
        self.commit(work, "b.txt", "two", "w2")
        self.assertIn("Rejected", run(work, "push", "origin"))
        self.assertEqual(ref_value(server, "refs/heads/main"), s1)

        run(work, "fetch", "origin")
        self.assertEqual(ref_value(work, "refs/remotes/origin/main"), s1)


if __name__ == "__main__":
    unittest.main()