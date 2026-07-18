import signal
import unittest
from queue import Queue
from unittest.mock import Mock, patch

from image_explorer_manager import ImageExplorerManager
from utility import Utility


class ImageExplorerCleanupTest(unittest.TestCase):
    @patch.object(Utility, "run")
    def test_none_queue_never_runs_global_pkill(self, run):
        self.assertEqual((True, ""), ImageExplorerManager.pop_and_kill("nbdkit", None))
        run.assert_not_called()

    @patch.object(Utility, "run")
    @patch.object(Utility, "umount_warn_on_busy", return_value=(True, ""))
    def test_unmount_without_owned_processes_only_unmounts_destination(
        self, umount, run
    ):
        self.assertEqual(
            (True, ""),
            ImageExplorerManager._do_unmount("/mnt/rescuezilla.image.explorer"),
        )
        umount.assert_called_once_with("/mnt/rescuezilla.image.explorer")
        run.assert_not_called()

    def test_owned_process_receives_sigterm(self):
        process = Mock(pid=1234)
        queue = Queue()
        queue.put(process)
        self.assertEqual((True, ""), ImageExplorerManager.pop_and_kill("nbdkit", queue))
        process.send_signal.assert_called_once_with(signal.SIGTERM)
        process.wait.assert_called_once_with(10)


if __name__ == "__main__":
    unittest.main()
