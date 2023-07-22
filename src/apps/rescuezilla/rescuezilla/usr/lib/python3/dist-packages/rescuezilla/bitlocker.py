from tempfile import mkdtemp
import os.path

from utility import Utility, dumper, _
from parser.blkid import Blkid
from encryption import EncryptionState

#    "/dev/nvme0n1p3": {
#       "end": 68062019583,
#       "filesystem": "BitLocker",
#       "flags": "msftdata",
#       "size": 67939336192,
#       "start": 122683392,
#       "type": "part"
#     },


def _get_partition_info(drive_state: dict, partition_dev_node: str) -> dict:
    for drive, data in drive_state.items():
        if not partition_dev_node.startswith(drive):
            continue
        if partition_dev_node not in data.get("partitions", {}):
            continue
        return data["partitions"][partition_dev_node]


def _get_partition_info2(drive_dict: dict, drive_key: str, partition_key: str) -> dict:
    return drive_dict.get(drive_key, {}).get("partitions", {}).get(partition_key, {})


class BitLocker:
    @staticmethod
    def is_filesystem_bitlocker(filesystem_name: str) -> bool:
        return filesystem_name == "BitLocker"

    @staticmethod
    def show_hide_decryption_gui(drive_state: dict, partition_dev_node: str) -> bool:
        partition_info = _get_partition_info(drive_state, partition_dev_node)
        encryption_info = BitLocker.partition_encryption_state(partition_info)
        return encryption_info == EncryptionState.ENCRYPTED_AND_LOCKED

    @staticmethod
    def get_partition_icon_name(drive_dict: dict, drive_key: str, partition_key: str) -> str:
        """Returns either the drive_partition_not_encrypted or drive_partition_encrypted_and_locked or drive_partition_encrypted_and_unlocked"""
        partition_info = _get_partition_info2(drive_dict, drive_key, partition_key)
        encryption_info = BitLocker.partition_encryption_state(partition_info)
        if encryption_info == EncryptionState.ENCRYPTED_AND_LOCKED:
            return "drive_partition_encrypted_and_locked"
        elif encryption_info == EncryptionState.ENCRYPTED_AND_UNLOCKED:
            return "drive_partition_encrypted_and_unlocked"
        else:
            return "drive_partition_not_encrypted"

    @staticmethod
    def partition_encryption_state(partition_info: dict) -> EncryptionState:
        filesystem = partition_info.get("filesystem")
        if BitLocker.is_filesystem_bitlocker(filesystem):
            if "unencrypted_data" in partition_info:
                return EncryptionState.ENCRYPTED_AND_UNLOCKED
            else:
                return EncryptionState.ENCRYPTED_AND_LOCKED
        else:
            return EncryptionState.NOT_ENCRYPTED

    @staticmethod
    def mount_bitlocker_image_with_dislocker(partition_dev_node: str, password: str) -> tuple[dict, str]:
        print("mount_bitlocker_image_with_dislocker")
        tempfolder = mkdtemp(prefix=f"dislocker_{partition_dev_node.split('/')[-1]}_")
        password_bytes = f"{password}\n"
        cmd_string= f"dislocker-fuse -u {partition_dev_node} {tempfolder}"
        cmd = cmd_string.split(" ")
        try:
            process, flat_command_string, _ignored_ = Utility.run(
                f"Mounting bitlocked disk with dislocker",
                cmd,
                use_c_locale=True,
                input=password_bytes,
            )
        except FileNotFoundError as e:
            msg = _(f"Error attemping to run dislocker to decrypt the partition {partition_dev_node}.\n" + f"Command: {cmd_string}\nError:{e}")
            return None, msg
        if process.returncode != 0:
            msg = _(f"Error attemping to run dislocker to decrypt the partition {partition_dev_node}.\n" + f"Command: {flat_command_string}\nReturnCode: {process.returncode}\nOutput: {process.stdout}")
            return None, msg

        unencrypted_partition = os.path.join(tempfolder, "dislocker-file")
        print(f"Dislocker was able to mount the encrypted disk successfully at {unencrypted_partition}!")
        return BitLocker._parse_new_partition(unencrypted_partition), None

    @staticmethod
    def _parse_new_partition(filename: str):
        blkid_cmd_list = ["blkid", filename]
        process, flat_command_string, fail_description = Utility.run(f"blkid {filename}", blkid_cmd_list, use_c_locale=True)
        blkid_dict = Blkid.parse_blkid_output(process.stdout)[filename]

        parsed_dict = {"device_path": filename}

        conversion_table = {
            "TYPE": "filesystem",
            "LABEL": "os_label",
            "UUID": "uuid",
            "BLOCK_SIZE": "block_size",
        }

        for old_key, new_key in conversion_table.items():
            if old_key in blkid_dict:
                parsed_dict[new_key] = blkid_dict[old_key]

        dumper(parsed_dict)
        return parsed_dict

    @staticmethod
    def update_drive_state(drive_state: dict, partition: str, unencrypted_partition_info: dict):
        partition_info = _get_partition_info(drive_state, partition)
        partition_info["unencrypted_data"] = unencrypted_partition_info
