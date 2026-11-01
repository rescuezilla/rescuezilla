#!/bin/bash
# Quick snapshot-style testing helper script.
# It happens to generate some Python code on stdout
#
# This assists in updating the CombinedDriveState test file.
#
# Especially when certain commands change their output format etc.


# Array of drives from /dev/sda to /dev/sdn
declare -a drives=(
    "/dev/sda"
    "/dev/sdb"
    "/dev/sdc"
    "/dev/sdd"
    "/dev/sde"
    "/dev/sdf"
    "/dev/sdg"
    "/dev/sdh"
    "/dev/sdi"
)


shared_system_state() {
    # Run the commands to generally
    cat <<EOF
        # Output of "lsblk -o KNAME,NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL --paths --bytes --json"
        lsblk_json_output = """$(lsblk -o KNAME,NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL --paths --bytes --json)"""
        lsblk_json_dict = json.loads(lsblk_json_output)

        # Output of "blkid"
        blkid_dict = Blkid.parse_blkid_output("""$(blkid)
""")

        # Output of "os-prober"
        osprober_dict = OsProber.parse_os_prober_output("""
        $(os-prober)
""")
EOF
    echo 
}

generate_sfdisk_input_data() {
    local drives_array=("$@")

    echo "# Output of 'sfdisk --dump /dev/sdX'"
    for drive in "${drives_array[@]}"; do
    cat <<EOF
        sfdict_dict_dict["$drive"] = Sfdisk.parse_sfdisk_dump_output("""
        $(sfdisk --dump $drive)
""")
EOF
    done
    echo 
}

generate_parted_input_data() {
    local drives_array=("$@")

    for drive in "${drives_array[@]}"; do
        cat <<EOF
        parted_dict_dict["$drive"] = Parted.parse_parted_output("""
        $(parted -s $drive unit B print)
""")
EOF
    echo 
    done
    echo 
}


shared_system_state
generate_sfdisk_input_data "${drives[@]}" 
generate_parted_input_data "${drives[@]}" 
