
import tempfile

from utility import Utility, _

def _get_partition_info(drive_state, partition_dev_node):
    for drive, data in drive_state.items():
        if not partition_dev_node.startswith(drive):
            continue
        if partition_dev_node not in data.get("partitions", {}):
            continue
        return data["partitions"][partition_dev_node]

class BitLocker:

    @staticmethod
    def is_filesystem_bitlocker(filesystem_name: str) -> bool:
        return filesystem_name == "BitLocker"

    def show_hide_decryption_gui(drive_state, partition_dev_node: str):
        partition_info = _get_partition_info(drive_state, partition_dev_node)
        return BitLocker.is_filesystem_bitlocker(partition_info.get("filesystem"))

    def mount_bitlocker_image_with_dislocker(partition_dev_node: str, password: str):
        print("mount_bitlocker_image_with_dislocker")
        tempfolder = tempfile.mkdtemp(prefix=f"dislocker_{partition_dev_node.split('/')[-1]}_")
        password_bytes = f"{password}\n"
        cmd = f"dislocker-fuse -u {partition_dev_node} {tempfolder}".split(" ")
        process, flat_command_string, _ = Utility.run(f"Mounting bitlocked disk with dislocker", cmd, use_c_locale=True, input=password_bytes)
        if process.returncode != 0:
            msg = _(f"Error attemptng to run dislocker to decrypt the partition {partition_dev_node}.\n" +
            f"Command: {flat_command_string}\nReturnCode: {process.returncode}\nOutput: {process.stdout}")
            return msg
        print("Dislocker was able to mount the encrypted disk successfully!")
        return None


