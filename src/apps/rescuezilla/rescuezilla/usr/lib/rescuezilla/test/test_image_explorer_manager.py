import signal
import subprocess
import threading
import unittest
from queue import Queue
from unittest.mock import Mock, call, patch

from handler import Handler
from image_explorer_manager import ImageExplorerManager
from parser.clonezilla_image import ClonezillaImage
from parser.qemu_image import QemuImage
from utility import Utility
from wizard_state import (
    DECOMPRESSED_NBD_DEVICE,
    IMAGE_EXPLORER_DIR,
    JOINED_FILES_NBD_DEVICE,
    QEMU_NBD_NBD_DEVICE,
    RESCUEZILLA_MOUNT_TMP_DIR,
)


class ImageExplorerCleanupTest(unittest.TestCase):
    @staticmethod
    def make_manager():
        manager = ImageExplorerManager.__new__(ImageExplorerManager)
        manager.partclone_nbd_process_queue = Queue()
        manager.nbdkit_join_process_queue = Queue()
        manager.nbdkit_decompress_process_queue = Queue()
        manager.joined_nbd_device_owned = threading.Event()
        manager.decompressed_nbd_device_owned = threading.Event()
        manager.qemu_nbd_device_owned = threading.Event()
        manager.cleanup_lock = threading.Lock()
        return manager

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

    @patch.object(QemuImage, "deassociate_nbd")
    @patch.object(Utility, "run")
    @patch.object(Utility, "umount_warn_on_busy", return_value=(True, ""))
    def test_selected_qemu_without_owned_device_only_unmounts_destination(
        self, umount, run, deassociate_nbd
    ):
        manager = self.make_manager()
        manager.selected_image = QemuImage.__new__(QemuImage)
        self.assertTrue(hasattr(manager, "cleanup_owned_resources"))

        self.assertEqual(
            (True, ""), manager.cleanup_owned_resources(IMAGE_EXPLORER_DIR)
        )

        umount.assert_called_once_with(IMAGE_EXPLORER_DIR)
        run.assert_not_called()
        deassociate_nbd.assert_not_called()

    @patch.object(QemuImage, "deassociate_nbd")
    @patch.object(Utility, "run")
    @patch.object(Utility, "umount_warn_on_busy", return_value=(True, ""))
    def test_owned_server_without_device_attachment_is_killed_without_disconnect(
        self, _umount, run, deassociate_nbd
    ):
        manager = self.make_manager()
        process = Mock(pid=1234)
        manager.nbdkit_join_process_queue.put(process)
        self.assertTrue(hasattr(manager, "cleanup_owned_resources"))

        self.assertEqual(
            (True, ""), manager.cleanup_owned_resources(IMAGE_EXPLORER_DIR)
        )

        process.send_signal.assert_called_once_with(signal.SIGTERM)
        run.assert_not_called()
        deassociate_nbd.assert_not_called()

    @patch.object(Utility, "run")
    @patch.object(Utility, "umount_warn_on_busy", return_value=(True, ""))
    def test_concurrent_cleanup_disconnects_owned_device_once(self, _umount, run):
        manager = self.make_manager()
        manager.joined_nbd_device_owned.set()
        notices = Queue()
        release_first = threading.Event()
        disconnects = []
        errors = []

        class NotifyingLock:
            def __init__(self):
                self.lock = threading.Lock()

            def __enter__(self):
                notices.put(("lock", threading.current_thread().name))
                self.lock.acquire()

            def __exit__(self, *_args):
                self.lock.release()

        manager.cleanup_lock = NotifyingLock()

        def mocked_run(_description, command, **_kwargs):
            if command == ["modprobe", "nbd"]:
                thread_name = threading.current_thread().name
                notices.put(("modprobe", thread_name))
                if thread_name == "first":
                    release_first.wait(2)
            elif command[0] == "nbd-client":
                disconnects.append(command)
            return Mock(returncode=0), "", ""

        def cleanup():
            try:
                manager.cleanup_owned_resources(IMAGE_EXPLORER_DIR)
            except Exception as exception:
                errors.append(exception)

        run.side_effect = mocked_run
        first = threading.Thread(target=cleanup, name="first")
        second = threading.Thread(target=cleanup, name="second")
        first.start()
        while notices.get(timeout=2) != ("modprobe", "first"):
            pass
        second.start()
        second_notice = notices.get(timeout=2)
        release_first.set()
        first.join(2)
        second.join(2)

        self.assertEqual(("lock", "second"), second_notice)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual([], errors)
        self.assertEqual(
            [["nbd-client", "-disconnect", JOINED_FILES_NBD_DEVICE]],
            disconnects,
        )

    @patch.object(QemuImage, "deassociate_nbd", return_value=(True, ""))
    @patch.object(Utility, "run")
    @patch.object(Utility, "umount_warn_on_busy", return_value=(True, ""))
    def test_only_owned_devices_are_disconnected_and_success_clears_ownership(
        self, _umount, run, deassociate_nbd
    ):
        self.assertTrue(hasattr(ImageExplorerManager, "cleanup_owned_resources"))
        for ownership_name, expected_disconnect in (
            (
                "joined_nbd_device_owned",
                ["nbd-client", "-disconnect", JOINED_FILES_NBD_DEVICE],
            ),
            (
                "decompressed_nbd_device_owned",
                ["nbd-client", "-disconnect", DECOMPRESSED_NBD_DEVICE],
            ),
            ("qemu_nbd_device_owned", QEMU_NBD_NBD_DEVICE),
        ):
            with self.subTest(ownership_name=ownership_name):
                manager = self.make_manager()
                ownership = getattr(manager, ownership_name)
                ownership.set()
                run.reset_mock()
                deassociate_nbd.reset_mock()
                run.return_value = (Mock(returncode=0), "", "")

                self.assertEqual(
                    (True, ""), manager.cleanup_owned_resources(IMAGE_EXPLORER_DIR)
                )

                self.assertFalse(ownership.is_set())
                if ownership_name == "qemu_nbd_device_owned":
                    deassociate_nbd.assert_called_once_with(expected_disconnect)
                    self.assertEqual(["modprobe", "nbd"], run.call_args_list[0].args[1])
                    self.assertEqual(1, run.call_count)
                else:
                    deassociate_nbd.assert_not_called()
                    self.assertEqual(
                        [
                            ["modprobe", "nbd"],
                            expected_disconnect,
                        ],
                        [item.args[1] for item in run.call_args_list],
                    )

    @patch("handler.Gtk.main_quit")
    @patch("handler.subprocess.Popen")
    @patch.object(ImageExplorerManager, "_do_unmount", return_value=(True, ""))
    def test_handler_exit_uses_manager_owned_cleanup(self, unmount, _popen, _main_quit):
        handler = Handler.__new__(Handler)
        handler.image_explorer_manager = Mock()
        handler.image_explorer_manager.cleanup_owned_resources.return_value = (True, "")

        handler.exit_app()

        handler.image_explorer_manager.cleanup_owned_resources.assert_called_once_with(
            IMAGE_EXPLORER_DIR
        )
        unmount.assert_called_once_with(
            RESCUEZILLA_MOUNT_TMP_DIR, is_deassociate_qemu_nbd_device=False
        )

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
    def test_device_ownership_is_set_only_after_successful_association(
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
        manager = self.make_manager()

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

        ownership_at_cancellation_checks = []
        cleanup_count = 0

        def stop_after_decompressor_association(*_args):
            nonlocal cleanup_count
            cleanup_count += 1
            if cleanup_count in (2, 3, 4, 5):
                ownership_at_cancellation_checks.append(
                    (
                        cleanup_count,
                        manager.joined_nbd_device_owned.is_set(),
                        manager.decompressed_nbd_device_owned.is_set(),
                        manager.nbdkit_decompress_process_queue.qsize(),
                    )
                )
            if cleanup_count == 5:
                return True
            return False

        manager._check_stop_and_cleanup = Mock(
            side_effect=stop_after_decompressor_association
        )

        manager._do_mount_command(
            Mock(), Mock(), image, "sda1", "/mnt/rescuezilla.image.explorer"
        )

        self.assertEqual(
            [
                (2, False, False, 0),
                (3, True, False, 0),
                (4, True, False, 1),
                (5, True, True, 1),
            ],
            ownership_at_cancellation_checks,
        )
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
        supports.side_effect = lambda args: (
            args
            == [
                "--filter=truncate",
                "--filter=gzip",
                "file",
            ]
        )
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
        which.side_effect = lambda name: (
            None if name in {"nbdkit", "nbd-client"} else "/usr/bin/" + name
        )
        self.assertEqual(
            ["nbd-client", "nbdkit"],
            ImageExplorerManager._missing_commands(["nbdkit", "mount", "nbd-client"]),
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
        return_value=[
            "blkid",
            "findmnt",
            "modprobe",
            "mount",
            "nbd-client",
            "qemu-img",
            "qemu-nbd",
            "umount",
        ],
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
            [
                "blkid",
                "findmnt",
                "modprobe",
                "mount",
                "nbd-client",
                "qemu-img",
                "qemu-nbd",
                "umount",
            ]
        )
        self.assertEqual(
            [
                call(
                    callback,
                    False,
                    "Image Explorer requires: blkid, findmnt, modprobe, mount, "
                    "nbd-client, qemu-img, qemu-nbd, umount",
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

    @patch("image_explorer_manager.subprocess.Popen")
    @patch.object(Utility, "interruptable_run")
    @patch.object(ImageExplorerManager, "_do_unmount", return_value=(True, ""))
    @patch("image_explorer_manager.os.path.exists", return_value=True)
    @patch.object(ImageExplorerManager, "_missing_commands", return_value=[])
    @patch("image_explorer_manager.GLib.idle_add")
    def test_qemu_association_failure_callbacks_once_without_mounting(
        self,
        idle_add,
        _missing_commands,
        _exists,
        _unmount,
        interruptable_run,
        popen,
    ):
        manager = ImageExplorerCleanupTest.make_manager()
        manager._check_stop_and_cleanup = Mock(return_value=False)
        image = QemuImage.__new__(QemuImage)
        image.associate_nbd = Mock(return_value=(False, "qemu attach failed"))
        manager.selected_image = image
        interruptable_run.return_value = (Mock(returncode=0), "", "")
        popup = Mock()
        callback = Mock()

        manager._do_mount_command(
            popup, callback, image, "/dev/sda1", IMAGE_EXPLORER_DIR
        )

        self.assertFalse(manager.qemu_nbd_device_owned.is_set())
        self.assertEqual(
            1,
            idle_add.call_args_list.count(call(callback, False, "qemu attach failed")),
        )
        self.assertEqual(1, idle_add.call_args_list.count(call(popup.destroy)))
        self.assertNotIn(
            call(callback, True, unittest.mock.ANY), idle_add.call_args_list
        )
        self.assertEqual(1, interruptable_run.call_count)
        popen.assert_not_called()


class QemuImageAssociationTest(unittest.TestCase):
    @staticmethod
    def make_image():
        image = QemuImage.__new__(QemuImage)
        image.absolute_path = "/backup/disk.qcow2"
        image.timeout_seconds = 5
        return image

    @patch.object(QemuImage, "deassociate_nbd", return_value=(True, ""))
    @patch.object(Utility, "retry_run", return_value=(False, "device busy"))
    def test_connect_failure_does_not_disconnect_unknown_device(
        self, _retry_run, deassociate_nbd
    ):
        self.assertEqual(
            (False, "device busy"),
            self.make_image().associate_nbd(QEMU_NBD_NBD_DEVICE),
        )

        deassociate_nbd.assert_not_called()

    @patch.object(QemuImage, "deassociate_nbd", return_value=(True, ""))
    @patch.object(Utility, "retry_run")
    def test_readiness_failure_disconnects_only_new_association(
        self, retry_run, deassociate_nbd
    ):
        operations = []
        retry_results = iter(((True, ""), (False, "device not ready")))

        def retry(**kwargs):
            operations.append(kwargs["short_description"])
            return next(retry_results)

        retry_run.side_effect = retry
        deassociate_nbd.side_effect = lambda device: (
            operations.append("disconnect " + device) or (True, "")
        )

        self.assertEqual(
            (False, "device not ready"),
            self.make_image().associate_nbd(QEMU_NBD_NBD_DEVICE),
        )
        self.assertEqual(
            [
                "qemu-nbd associate with " + QEMU_NBD_NBD_DEVICE,
                "Run blkid until NBD device ready " + QEMU_NBD_NBD_DEVICE,
                "disconnect " + QEMU_NBD_NBD_DEVICE,
            ],
            operations,
        )


if __name__ == "__main__":
    unittest.main()
