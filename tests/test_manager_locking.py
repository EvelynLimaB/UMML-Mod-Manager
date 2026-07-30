import os
import tempfile
import unittest
from pathlib import Path

from umml_manager.locking import FileLock, LockError


class ManagerFileLockTests(unittest.TestCase):
    def test_lock_can_be_released_and_reacquired(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manager.lock"
            with FileLock(path, purpose="testing first acquisition"):
                self.assertTrue(path.is_file())
                if os.name == "nt":
                    self.assertTrue(path.read_bytes().startswith(b"0"))
            with FileLock(path, purpose="testing second acquisition"):
                self.assertTrue(path.is_file())

    def test_second_owner_fails_while_first_lock_is_held(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manager.lock"
            with FileLock(path, purpose="holding test lock"):
                with self.assertRaises(LockError):
                    with FileLock(path, purpose="competing for test lock"):
                        self.fail("the competing lock unexpectedly succeeded")


if __name__ == "__main__":
    unittest.main()
