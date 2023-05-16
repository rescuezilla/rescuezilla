import argparse
from typing import Dict, Any


def valid_compression_level(compression_format, compression_level):
    if compression_format == 'gzip':
        if compression_level < 0 or compression_level > 9:
            raise argparse.ArgumentTypeError("gzip compression level must be between 0 and 9")
    elif compression_format == 'zstd':
        if compression_level < 1 or compression_level > 19:
            raise argparse.ArgumentTypeError("zstd compression level must be between 1 and 19")
    elif compression_format == 'bzip2':
        if compression_level < 1 or compression_level > 9:
            raise argparse.ArgumentTypeError("bzip2 compression level must be between 1 and 9")
    else:
        raise argparse.ArgumentTypeError("Invalid compression format")
    return compression_level


def add_option_argument_with_mutually_exclusive_positional_arg(parser: argparse.ArgumentParser, name: str, help: str):
    pos_group = parser.add_mutually_exclusive_group(required=True)
    pos_group.add_argument(f"--{name}", nargs='?', default=None, type=str, help=help)
    pos_group.add_argument(f"{name}_positional_arg", nargs='?', default=None, type=str)

def process_mutually_exclusive_args(args: argparse.Namespace,
                                    args_dict: Dict[Any, Any], name):
    pos_arg_key =  f"{name}_positional_arg"
    value = getattr(args, name, None) or getattr(args, pos_arg_key, None)
    if value is not None:
        args_dict[name] = value
    if pos_arg_key in args_dict:
        del args_dict[pos_arg_key]

def process_partition_list(args_dict: Dict[Any, Any]):
    if 'partitions' in args_dict and 'all' in args_dict['partitions']:
        args_dict['partitions'] = ['all']


def parse_arguments(parser: argparse.ArgumentParser) -> argparse.Namespace:
    subparser = parser.add_subparsers(title="Rescuezilla command-line interface commands", metavar='command', dest="command")

    # Create subcommand parsers (subcommands, like git's CLI)
    backup_parser = subparser.add_parser('backup', help="Create backup image from source device")
    restore_parser = subparser.add_parser('restore', help="Restore image to destination device")
    clone_parser = subparser.add_parser('clone', help="Direct device-to-device without needing a third drive for temporary storage")
    verify_parser = subparser.add_parser('verify', help="Verify an image")
    mount_parser = subparser.add_parser('mount', help="Mount supported images to use system's file explorer to copy files")
    umount_parser = subparser.add_parser('umount', help="Unmount image mounted by the 'mount' command")

    # Add the --source parsing for all subcommands (except the umount subcommand which doesn't need it) with source can
    # additionally be specified as a positional argument
    add_option_argument_with_mutually_exclusive_positional_arg(backup_parser, "source", "Device to backup")
    add_option_argument_with_mutually_exclusive_positional_arg(restore_parser, "source", "Image to use")
    add_option_argument_with_mutually_exclusive_positional_arg(clone_parser, "source", "Source device to read")
    add_option_argument_with_mutually_exclusive_positional_arg(verify_parser, "source", "Image to verify")
    add_option_argument_with_mutually_exclusive_positional_arg(mount_parser, "source", "Image to mount")

    # Add the --destination argument parsing for all subcommands (except the verify subcommand which doesn't need it),
    # with destination can be additionally be specified as a positional argument
    add_option_argument_with_mutually_exclusive_positional_arg(backup_parser, "destination", "Destination folder to write backup to")
    add_option_argument_with_mutually_exclusive_positional_arg(restore_parser, "destination", "Restore backup image to destination device")
    add_option_argument_with_mutually_exclusive_positional_arg(clone_parser, "destination", "Destination drive to overwrite")
    add_option_argument_with_mutually_exclusive_positional_arg(mount_parser, "destination", "Destination folder to mount")
    add_option_argument_with_mutually_exclusive_positional_arg(umount_parser, "destination", "Destination folder to umount")

    # Add the --partitions for backup/restore/clone. TODO: Add validation to this
    backup_parser.add_argument('--partitions', default='all', nargs='+', type=str, help='The partitions to backup from the source drive')
    restore_parser.add_argument('--partitions', default='all', nargs='+', type=str, help='The partitions to restore from the source image')
    clone_parser.add_argument('--partitions', default='all', nargs='+', type=str, help='The partitions to clone from the source drive')

    # Add the --description parsing for backup subcommand
    backup_parser.add_argument('--description', type=str, help='Textual description of the backup image', default="")

    # Add the --compression-format for the backup command
    backup_parser.add_argument('--compression-format', type=str, choices=['gzip', 'none', 'zstd', 'bzip2'], default='gzip', help='The compression format')
    #TODO fix
    backup_parser.add_argument('--compression-level', type=lambda x: valid_compression_level("gzip", int(x)), default=9)

    backup_parser.add_argument('--post-operation-action', type=str, choices=['none', 'shutdown', 'reboot'], default='none', help='Operation to do after backup finished')
    backup_parser.add_argument('--rescue', action='store_true', default=False, help="Use partclone's --rescue option. Use with caution: enabling may suppress important errors")

    restore_parser.add_argument('--overwrite-partition-table', action='store_true', default=True, help="Overwrite the destination device's partition table")
    restore_parser.add_argument('--rescue', action='store_true', default=False, help="Use partclone's --rescue option. Use with caution: enabling may suppress important errors")

    clone_parser.add_argument('--overwrite-partition-table', action='store_true', default=True, help="Overwrite the destination device's partition table")
    clone_parser.add_argument('--rescue', action='store_true', default=False, help="Use partclone's --rescue option. Use with caution: enabling may suppress important errors")

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)

    # Do post-processing cleanup of arguments
    args_dict = vars(args).copy()
    process_mutually_exclusive_args(args=args, args_dict=args_dict, name='source')
    process_mutually_exclusive_args(args=args, args_dict=args_dict, name='destination')
    process_partition_list(args_dict=args_dict)
    new_args = argparse.Namespace(**args_dict)
    return new_args
