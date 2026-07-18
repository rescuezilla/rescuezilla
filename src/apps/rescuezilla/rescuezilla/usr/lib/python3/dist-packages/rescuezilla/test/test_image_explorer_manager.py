import signal
import unittest
from queue import Queue
from unittest.mock import Mock, patch

from image_explorer_manager import ImageExplorerManager
from parser.clonezilla_image import ClonezillaImage
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

    @patch("image_explorer_manager.GLib.idle_add")
    @patch.object(Utility, "print_cli_friendly", return_value="")
    @patch.object(Utility, "retry_run", return_value=(True, ""))
    @patch.object(Utility, "interruptable_run")
    @patch.object(ImageExplorerManager, "_do_unmount", return_value=(True, ""))
    @patch("image_explorer_manager.os.path.exists", return_value=True)
    @patch("image_explorer_manager.shutil.which", return_value="/usr/bin/nbdkit")
    @patch("image_explorer_manager.subprocess.Popen")
    def test_decompressor_is_owned_before_cancellation_cleanup(
        self,
        popen,
        _which,
        _exists,
        _unmount,
        interruptable_run,
        _retry_run,
        _print_cli_friendly,
        _idle_add,
    ):
        manager = ImageExplorerManager.__new__(ImageExplorerManager)
        manager.partclone_nbd_process_queue = Queue()
        manager.nbdkit_join_process_queue = Queue()
        manager.nbdkit_decompress_process_queue = Queue()

        image = ClonezillaImage.__new__(ClonezillaImage)
        image.image_format_dict_dict = {
            "sda1": {
                "absolute_filename_glob_list": ["/backup/sda1.img"],
                "compression": "uncompressed",
                "type": "partclone",
            }
        }
        manager.selected_image = image

        join_process = Mock(pid=1234)
        decompress_process = Mock(pid=5678)
        popen.side_effect = [join_process, decompress_process]
        interruptable_run.return_value = (Mock(returncode=0), "", "")

        cleanup_queue_sizes = []
        cleanup_count = 0

        def stop_after_decompressor_starts(*_args):
            nonlocal cleanup_count
            cleanup_count += 1
            if cleanup_count == 4:
                cleanup_queue_sizes.append(
                    manager.nbdkit_decompress_process_queue.qsize()
                )
                return True
            return False

        manager._check_stop_and_cleanup = Mock(
            side_effect=stop_after_decompressor_starts
        )

        manager._do_mount_command(
            Mock(), Mock(), image, "sda1", "/mnt/rescuezilla.image.explorer"
        )

        self.assertEqual([1], cleanup_queue_sizes)
        self.assertIs(
            decompress_process,
            manager.nbdkit_decompress_process_queue.get_nowait(),
        )


if __name__ == "__main__":
    unittest.main()
