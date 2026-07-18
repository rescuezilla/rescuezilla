import signal
import subprocess
import unittest
from queue import Queue
from unittest.mock import Mock, call, patch

from image_explorer_manager import ImageExplorerManager
from parser.clonezilla_image import ClonezillaImage
from parser.qemu_image import QemuImage
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
    @patch.object(
        ImageExplorerManager,
        "_partclone_capability_error",
        return_value=(["--filter=gzip", "file"], ""),
    )
    @patch("image_explorer_manager.os.path.exists", return_value=True)
    @patch("image_explorer_manager.subprocess.Popen")
    def test_decompressor_is_owned_before_cancellation_cleanup(
        self,
        popen,
        _exists,
        _capability_error,
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
        decompress_command = popen.call_args_list[1].args[0]
        self.assertEqual(1, decompress_command.count("--filter=truncate"))
        self.assertEqual(
            ["--filter=truncate", "--filter=gzip", "file"],
            decompress_command[5:8],
        )


class ImageExplorerCapabilityTest(unittest.TestCase):
    @patch.object(ImageExplorerManager, "_nbdkit_supports")
    def test_gzip_prefers_modern_filter(self, supports):
        supports.side_effect = lambda args: args == [
            "--filter=truncate",
            "--filter=gzip",
            "file",
        ]
        self.assertEqual(
            ["--filter=gzip", "file"],
            ImageExplorerManager._nbdkit_compression_args("gzip"),
        )

    @patch.object(ImageExplorerManager, "_nbdkit_supports")
    def test_gzip_falls_back_to_legacy_plugin(self, supports):
        supports.side_effect = lambda args: args == ["--filter=truncate", "gzip"]
        self.assertEqual(
            ["gzip"], ImageExplorerManager._nbdkit_compression_args("gzip")
        )

    @patch.object(ImageExplorerManager, "_nbdkit_supports", return_value=False)
    def test_missing_gzip_capability_returns_none(self, supports):
        self.assertIsNone(ImageExplorerManager._nbdkit_compression_args("gzip"))

    @patch.object(ImageExplorerManager, "_nbdkit_supports", return_value=True)
    def test_xz_and_uncompressed_use_file_plugin(self, supports):
        self.assertEqual(
            ["--filter=xz", "file"],
            ImageExplorerManager._nbdkit_compression_args("xz"),
        )
        self.assertEqual(
            ["file"],
            ImageExplorerManager._nbdkit_compression_args("uncompressed"),
        )

    @patch("image_explorer_manager.shutil.which")
    def test_missing_commands_are_sorted(self, which):
        which.side_effect = (
            lambda name: None
            if name in {"nbdkit", "nbd-client"}
            else "/usr/bin/" + name
        )
        self.assertEqual(
            ["nbd-client", "nbdkit"],
            ImageExplorerManager._missing_commands(
                ["nbdkit", "mount", "nbd-client"]
            ),
        )

    @patch("image_explorer_manager.subprocess.run")
    def test_nbdkit_probe_uses_dump_plugin(self, run):
        run.return_value.returncode = 0

        self.assertTrue(
            ImageExplorerManager._nbdkit_supports(["--filter=truncate", "split"])
        )

        run.assert_called_once_with(
            ["nbdkit", "--filter=truncate", "split", "--dump-plugin"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    @patch.object(
        ImageExplorerManager,
        "_missing_commands",
        return_value=["nbd-client", "partclone-nbd"],
    )
    def test_partclone_preflight_reports_missing_commands(self, _missing):
        self.assertEqual(
            (
                None,
                "Image Explorer requires: nbd-client, partclone-nbd",
            ),
            ImageExplorerManager._partclone_capability_error("uncompressed"),
        )

    @patch.object(ImageExplorerManager, "_nbdkit_compression_args")
    @patch.object(ImageExplorerManager, "_nbdkit_supports", return_value=False)
    @patch.object(ImageExplorerManager, "_missing_commands", return_value=[])
    def test_partclone_preflight_requires_split_and_truncate(
        self, _missing, _supports, compression_args
    ):
        self.assertEqual(
            (None, "nbdkit is missing the split plugin or truncate filter."),
            ImageExplorerManager._partclone_capability_error("uncompressed"),
        )
        compression_args.assert_not_called()

    @patch("image_explorer_manager.subprocess.Popen")
    @patch.object(Utility, "interruptable_run")
    @patch.object(ImageExplorerManager, "_do_unmount")
    @patch("image_explorer_manager.os.mkdir")
    @patch("image_explorer_manager.os.path.exists")
    @patch.object(
        ImageExplorerManager,
        "_partclone_capability_error",
        return_value=(None, "Image Explorer requires: nbd-client"),
    )
    @patch("image_explorer_manager.GLib.idle_add")
    def test_partclone_preflight_precedes_mount_mutation(
        self,
        idle_add,
        capability_error,
        exists,
        mkdir,
        unmount,
        interruptable_run,
        popen,
    ):
        manager = ImageExplorerManager.__new__(ImageExplorerManager)
        image = ClonezillaImage.__new__(ClonezillaImage)
        image.image_format_dict_dict = {
            "sda1": {
                "absolute_filename_glob_list": ["/backup/sda1.img"],
                "compression": "uncompressed",
                "type": "partclone",
            }
        }
        manager.selected_image = image
        popup = Mock()
        callback = Mock()

        manager._do_mount_command(
            popup, callback, image, "sda1", "/mnt/rescuezilla.image.explorer"
        )

        capability_error.assert_called_once_with("uncompressed")
        self.assertEqual(
            [
                call(callback, False, "Image Explorer requires: nbd-client"),
                call(popup.destroy),
            ],
            idle_add.call_args_list,
        )
        exists.assert_not_called()
        mkdir.assert_not_called()
        unmount.assert_not_called()
        interruptable_run.assert_not_called()
        popen.assert_not_called()

    @patch("image_explorer_manager.subprocess.Popen")
    @patch.object(Utility, "interruptable_run")
    @patch.object(ImageExplorerManager, "_do_unmount")
    @patch("image_explorer_manager.os.path.exists")
    @patch.object(
        ImageExplorerManager,
        "_missing_commands",
        return_value=["qemu-img", "qemu-nbd"],
    )
    @patch("image_explorer_manager.GLib.idle_add")
    def test_qemu_preflight_precedes_device_disconnect(
        self,
        idle_add,
        missing_commands,
        exists,
        unmount,
        interruptable_run,
        popen,
    ):
        manager = ImageExplorerManager.__new__(ImageExplorerManager)
        image = QemuImage.__new__(QemuImage)
        manager.selected_image = image
        image.associate_nbd = Mock()
        popup = Mock()
        callback = Mock()

        manager._do_mount_command(
            popup, callback, image, "/dev/sda1", "/mnt/rescuezilla.image.explorer"
        )

        missing_commands.assert_called_once_with(
            ["blkid", "nbd-client", "qemu-img", "qemu-nbd"]
        )
        self.assertEqual(
            [
                call(
                    callback,
                    False,
                    "Image Explorer requires: qemu-img, qemu-nbd",
                ),
                call(popup.destroy),
            ],
            idle_add.call_args_list,
        )
        exists.assert_not_called()
        unmount.assert_not_called()
        interruptable_run.assert_not_called()
        image.associate_nbd.assert_not_called()
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
