#!/bin/bash
# ============================================================
#  Live Server Cloner to ISO  —  ReaR-style Archive Mode
#  Streams a running remote Linux server into a .tar.gz
#  archive stored on a local disk / mount point.
#
#  Dependencies: zenity, sshpass, ssh, tar, parted, mkfs.ext4
#  Author: Custom Rescuezilla Integration
# ============================================================

set -uo pipefail

# Ensure X11 display and authority for root when launched via sudo/desktop
[ -z "${DISPLAY:-}" ] && export DISPLAY=":0"
if [ -z "${XAUTHORITY:-}" ] && [ -f "/home/ubuntu/.Xauthority" ]; then
    export XAUTHORITY="/home/ubuntu/.Xauthority"
fi
xhost +local:root &>/dev/null || true

TOOL_NAME="Live Server Cloner to ISO"
LOG_FILE="/tmp/p2v-tool-$(date +%Y%m%d-%H%M%S).log"
PERM_LOG="/var/log/p2v-cloner.log"
MOUNT_POINT="/mnt/p2v-destination"

# ── Helpers ──────────────────────────────────────────────────

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE" >> "$PERM_LOG" 2>/dev/null || true
}

die() {
    log "FATAL: $1"
    local detail="${2:-}"
    local body="❌  <b>Fatal error:</b>\n\n$1"
    if [[ -n "$detail" ]]; then
        body+="\n\n<b>Details:</b>\n<tt>$detail</tt>"
    fi
    body+="\n\nSee log: <tt>$LOG_FILE</tt>"
    zenity --error \
        --title="$TOOL_NAME — Error" \
        --width=560 \
        --text="$body" 2>/dev/null
    exit 1
}

info() {
    zenity --info \
        --title="$TOOL_NAME" \
        --width=500 \
        --text="$1" 2>/dev/null
}

confirm() {
    zenity --question \
        --title="$TOOL_NAME — Confirm" \
        --width=520 \
        --text="$1" 2>/dev/null
}

check_deps() {
    local missing=()
    for cmd in zenity sshpass ssh tar parted mkfs.ext4 lsblk; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        zenity --error \
            --title="$TOOL_NAME — Missing Dependencies" \
            --width=500 \
            --text="❌ Missing tools: <b>${missing[*]}</b>\n\nRun:\n<tt>sudo apt-get install -y ${missing[*]}</tt>" 2>/dev/null
        exit 1
    fi
}

# ── Step 1: Collect Connection Details ───────────────────────

gather_inputs() {
    FORM=$(zenity --forms \
        --title="$TOOL_NAME — Remote Server" \
        --text="🖥️  <b>Enter Remote Server Details</b>\n\nThis tool will SSH into the running server and stream\nits filesystem into a compressed archive on your local disk." \
        --width=520 \
        --add-entry="Server IP Address (e.g. 192.168.1.100)" \
        --add-entry="SSH Username (e.g. root)" \
        --add-password="SSH Password" \
        --add-entry="SSH Port (default: 22)" \
        --separator="|" 2>/dev/null) || die "User cancelled."

    SERVER_IP=$(echo "$FORM"   | cut -d'|' -f1 | xargs)
    SSH_USER=$(echo "$FORM"    | cut -d'|' -f2 | xargs)
    SSH_PASS=$(echo "$FORM"    | cut -d'|' -f3)
    SSH_PORT=$(echo "$FORM"    | cut -d'|' -f4 | xargs)
    SSH_PORT=${SSH_PORT:-22}

    [[ -z "$SERVER_IP" ]] && die "Server IP cannot be empty."
    [[ -z "$SSH_USER"  ]] && die "SSH Username cannot be empty."
    [[ -z "$SSH_PASS"  ]] && die "SSH Password cannot be empty."

    # Build destination choices: Partitions (keep data) + Whole Disks (format option)
    DISK_LIST=()
    local default_selected=0

    # 1. Existing partitions with supported filesystems (ext4, xfs, btrfs, vfat, exfat, ntfs)
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        NAME=$(echo "$line" | awk '{print $1}')
        SIZE=$(echo "$line" | awk '{print $2}')
        FSTYPE=$(echo "$line" | awk '{print $3}')
        MOUNT=$(echo "$line" | awk '{print $4}')
        LABEL=$(echo "$line" | cut -d' ' -f5-)

        DEV="/dev/$NAME"
        DESC="${SIZE} | ${FSTYPE:-ext4} | KEEP EXISTING DATA"
        [[ -n "$LABEL" ]] && DESC+=" [${LABEL}]"
        [[ -n "$MOUNT" ]] && DESC+=" (mounted on ${MOUNT})"

        if [[ $default_selected -eq 0 ]]; then
            DISK_LIST+=(TRUE "$DEV" "$DESC")
            default_selected=1
        else
            DISK_LIST+=(FALSE "$DEV" "$DESC")
        fi
    done < <(lsblk -r -n -o NAME,SIZE,FSTYPE,MOUNTPOINT,LABEL 2>/dev/null | grep -E "part" | grep -E "ext4|xfs|btrfs|vfat|exfat|ntfs")

    # 2. Raw disks for explicit wipe & format
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        NAME=$(echo "$line" | awk '{print $1}')
        SIZE=$(echo "$line" | awk '{print $2}')
        MODEL=$(echo "$line" | cut -d' ' -f3-)
        DEV="/dev/$NAME"
        DESC="${SIZE} | FORMAT WHOLE DISK [${MODEL}]"
        if [[ $default_selected -eq 0 ]]; then
            DISK_LIST+=(TRUE "$DEV" "$DESC")
            default_selected=1
        else
            DISK_LIST+=(FALSE "$DEV" "$DESC")
        fi
    done < <(lsblk -d -n -o NAME,SIZE,MODEL 2>/dev/null | grep -v -E "loop|sr|nbd")

    if [[ ${#DISK_LIST[@]} -eq 0 ]]; then
        die "No local disks or partitions detected. Attach your USB storage drive."
    fi

    DEST_CHOICE=$(zenity --list \
        --title="$TOOL_NAME — Destination Storage" \
        --text="💾  <b>Select where to save the cloned server archive:</b>\n\n• Partitions labeled <b>KEEP EXISTING DATA</b> will <u>NOT</u> be erased.\n• Choosing a <b>FORMAT WHOLE DISK</b> option will erase that entire drive." \
        --width=680 --height=400 \
        --radiolist \
        --column="Select" \
        --column="Target" \
        --column="Details" \
        "${DISK_LIST[@]}" 2>/dev/null) || die "User cancelled."

    [[ -z "$DEST_CHOICE" ]] && die "No destination selected."

    OPTIONS=$(zenity --forms \
        --title="$TOOL_NAME — Archive Options" \
        --text="📦  <b>Archive Settings</b>" \
        --width=520 \
        --add-entry="Archive name (no extension, e.g. server-backup)" \
        --add-entry="Extra SSH options (leave blank for none)" \
        --separator="|" 2>/dev/null) || die "User cancelled."

    ARCHIVE_NAME=$(echo "$OPTIONS" | cut -d'|' -f1 | xargs)
    EXTRA_SSH=$(echo "$OPTIONS"    | cut -d'|' -f2 | xargs)
    ARCHIVE_NAME=${ARCHIVE_NAME:-"p2v-$(date +%Y%m%d-%H%M)"}

    log "Target selected: $DEST_CHOICE | Archive name: $ARCHIVE_NAME"
}

# ── Step 2: Test SSH Connection ──────────────────────────────

test_ssh() {
    log "Testing SSH connection to $SSH_USER@$SERVER_IP:$SSH_PORT ..."

    SSH_TEST_OUTPUT=$(sshpass -p "$SSH_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -o ConnectTimeout=10 \
        -o BatchMode=no \
        -p "$SSH_PORT" \
        "$SSH_USER@$SERVER_IP" \
        "uname -n; uname -r" 2>&1) || {
            die "Cannot connect to $SERVER_IP:$SSH_PORT via SSH." "$SSH_TEST_OUTPUT"
        }

    log "SSH connection successful: $SSH_TEST_OUTPUT"

    REMOTE_INFO=$(sshpass -p "$SSH_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -p "$SSH_PORT" \
        "$SSH_USER@$SERVER_IP" \
        "echo '--- Hostname ---'; uname -n
         echo '--- OS ---'; cat /etc/os-release 2>/dev/null | grep PRETTY_NAME || true
         echo '--- Disk Usage ---'; df -h / 2>/dev/null
         echo '--- Memory ---'; free -h 2>/dev/null" 2>/dev/null) || true

    log "Remote info: $REMOTE_INFO"

    confirm "✅  <b>Connected to $SERVER_IP successfully!</b>\n\n<tt>$REMOTE_INFO</tt>\n\nProceed with capture?" \
        || die "User cancelled after connection test."
}

# ── Step 3: Prepare Destination ──────────────────────────────

prepare_destination() {
    log "Preparing destination: $DEST_CHOICE"
    mkdir -p "$MOUNT_POINT"

    DEV_TYPE=$(lsblk -n -o TYPE "$DEST_CHOICE" 2>/dev/null | head -1 | xargs)

    if [[ "$DEV_TYPE" == "part" ]]; then
        # Existing partition: NEVER WIPE OR FORMAT
        log "Using existing partition $DEST_CHOICE (preserving data)"
        EXISTING_MOUNT=$(lsblk -n -o MOUNTPOINT "$DEST_CHOICE" 2>/dev/null | head -1 | xargs)
        if [[ -n "$EXISTING_MOUNT" ]] && [[ "$EXISTING_MOUNT" != "$MOUNT_POINT" ]]; then
            TARGET_DIR="$EXISTING_MOUNT"
        else
            mountpoint -q "$MOUNT_POINT" || mount "$DEST_CHOICE" "$MOUNT_POINT" >> "$LOG_FILE" 2>&1 \
                || die "Failed to mount partition $DEST_CHOICE to $MOUNT_POINT" "$(tail -n 10 "$LOG_FILE")"
            TARGET_DIR="$MOUNT_POINT"
        fi
    else
        # Raw disk: Ask for explicit confirmation before formatting
        confirm "⚠️  <b>CRITICAL CONFIRMATION:</b>\n\nYou selected whole disk: <b>$DEST_CHOICE</b>\n\nAll existing data and partitions on $DEST_CHOICE will be <b>PERMANENTLY ERASED</b>.\n\nAre you sure you want to format $DEST_CHOICE as ext4?" \
            || die "User cancelled disk format."

        log "Wiping and formatting $DEST_CHOICE as ext4..."
        wipefs -a "$DEST_CHOICE"             >> "$LOG_FILE" 2>&1 || true
        parted -s "$DEST_CHOICE" mklabel gpt >> "$LOG_FILE" 2>&1
        parted -s "$DEST_CHOICE" mkpart primary ext4 0% 100% >> "$LOG_FILE" 2>&1
        sleep 2

        DEST_PART="${DEST_CHOICE}1"
        [[ "$DEST_CHOICE" =~ nvme ]] && DEST_PART="${DEST_CHOICE}p1"

        mkfs.ext4 -F -L "P2V-DEST" "$DEST_PART" >> "$LOG_FILE" 2>&1 \
            || die "Failed to format $DEST_PART as ext4" "$(tail -n 10 "$LOG_FILE")"

        mountpoint -q "$MOUNT_POINT" && umount "$MOUNT_POINT" || true
        mount "$DEST_PART" "$MOUNT_POINT" >> "$LOG_FILE" 2>&1 \
            || die "Failed to mount $DEST_PART to $MOUNT_POINT" "$(tail -n 10 "$LOG_FILE")"
        TARGET_DIR="$MOUNT_POINT"
    fi

    ARCHIVE_PATH="$TARGET_DIR/${ARCHIVE_NAME}.tar.gz"
    METADATA_PATH="$TARGET_DIR/${ARCHIVE_NAME}-info.txt"
    log "Archive target set to: $ARCHIVE_PATH"
}

# ── Step 4: Save Remote System Metadata ───────────────────────

save_metadata() {
    log "Saving remote system metadata..."
    sshpass -p "$SSH_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -p "$SSH_PORT" \
        "$SSH_USER@$SERVER_IP" \
        "echo '=== P2V Capture Metadata ==='
         echo 'Captured: $(date)'
         echo ''
         echo '--- System Info ---'
         uname -a
         echo ''
         echo '--- OS Release ---'
         cat /etc/os-release 2>/dev/null
         echo ''
         echo '--- Disk Layout ---'
         lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT 2>/dev/null
         echo ''
         echo '--- Filesystem Table (/etc/fstab) ---'
         cat /etc/fstab 2>/dev/null
         echo ''
         echo '--- Network Interfaces ---'
         ip -brief addr 2>/dev/null || ifconfig 2>/dev/null
         echo ''
         echo '--- Kernel Modules ---'
         lsmod | head -30 2>/dev/null
         echo ''
         echo '--- CPU & Memory ---'
         lscpu 2>/dev/null | grep -E 'Model name|CPU\(s\):' || true
         free -h 2>/dev/null" \
        > "$METADATA_PATH" 2>>"$LOG_FILE" || log "Warning: metadata collection had non-fatal errors"

    log "Metadata saved to $METADATA_PATH"
}

# ── Step 5: Live Capture Over SSH Stream ──────────────────────

run_capture() {
    log "Starting live capture from $SERVER_IP ..."

    # Exclude virtual filesystems, cache, and snap loops
    EXCLUDES="--one-file-system \
              --exclude=/proc --exclude=/sys --exclude=/dev --exclude=/tmp \
              --exclude=/run --exclude=/mnt --exclude=/media --exclude=/snap \
              --exclude=/lost+found --exclude=/var/cache/apt \
              --exclude=/var/tmp --exclude='*.iso' --exclude='*.vmdk' --exclude='*.qcow2'"

    REMOTE_TAR_CMD="tar $EXCLUDES -czpf - / 2>/tmp/p2v-tar-errors.txt"
    log "Remote tar command: $REMOTE_TAR_CMD"

    sshpass -p "$SSH_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -o ServerAliveInterval=15 \
        -o ServerAliveCountMax=6 \
        -p "$SSH_PORT" \
        "$SSH_USER@$SERVER_IP" \
        "$REMOTE_TAR_CMD" \
        > "$ARCHIVE_PATH" 2>>"$LOG_FILE" &

    SSH_PID=$!
    log "SSH stream PID: $SSH_PID"

    START_TIME=$(date +%s)
    PREV_BYTES=0

    # Real-time 1-second transfer speed & progress reporting
    (
        while kill -0 $SSH_PID 2>/dev/null; do
            sleep 1
            NOW=$(date +%s)
            ELAPSED=$((NOW - START_TIME))
            MIN=$((ELAPSED / 60))
            SEC=$((ELAPSED % 60))

            CURR_BYTES=$(stat -c%s "$ARCHIVE_PATH" 2>/dev/null || echo 0)
            CURR_MB=$((CURR_BYTES / 1048576))

            DIFF_BYTES=$((CURR_BYTES - PREV_BYTES))
            PREV_BYTES=$CURR_BYTES
            SPEED_MBPS=$(awk -v b="$DIFF_BYTES" 'BEGIN { printf "%.1f", b / 1048576 }')

            echo "# 📡 <b>Streaming Live Filesystem from $SERVER_IP</b>\n\n📦 <b>Captured:</b> ${CURR_MB} MB\n⚡ <b>Transfer Speed:</b> ${SPEED_MBPS} MB/s\n⏱️ <b>Elapsed:</b> $(printf '%02d:%02d' $MIN $SEC)\n💾 <b>Saving to:</b> <tt>$(basename "$ARCHIVE_PATH")</tt>\n\n<i>Do NOT close this window or disconnect the drive.</i>"
        done
        echo "# Stream finished. Finalizing archive..."
    ) | zenity --progress \
        --title="$TOOL_NAME — Live Capture" \
        --text="📡 Connecting to $SERVER_IP and initializing stream..." \
        --width=580 \
        --pulsate \
        --auto-close 2>/dev/null || {
            kill -9 $SSH_PID 2>/dev/null || true
            die "Capture cancelled by user."
        }

    wait $SSH_PID || SSH_EXIT=$?
    SSH_EXIT=${SSH_EXIT:-0}
    log "SSH stream completed with exit code: $SSH_EXIT"

    # Copy log file to destination directory for persistence
    cp -f "$LOG_FILE" "$TARGET_DIR/${ARCHIVE_NAME}.log" 2>/dev/null || true
}

# ── Step 6: Verify & Report ───────────────────────────────────

verify_and_report() {
    log "Verifying archive..."
    sync

    ARCHIVE_SIZE=$(du -sh "$ARCHIVE_PATH" 2>/dev/null | awk '{print $1}')
    FREE_SPACE=$(df -h "$TARGET_DIR" 2>/dev/null | tail -1 | awk '{print $4}')

    REPORT="✅  <b>Capture Complete!</b>

📦  Archive:       <tt>${ARCHIVE_NAME}.tar.gz</tt>
💾  Size:          <b>$ARCHIVE_SIZE</b>
💿  Storage:       <tt>$DEST_CHOICE</tt>
🗂  Location:      <tt>$ARCHIVE_PATH</tt>
📋  Metadata:      <tt>${ARCHIVE_NAME}-info.txt</tt>
📄  Log:           <tt>${ARCHIVE_NAME}.log</tt>
💡  Free space:    $FREE_SPACE remaining

🔧  <b>To restore this archive to a new VM:</b>
1. Boot target VM from Rescuezilla USB
2. Mount your backup storage:  <tt>mount /dev/sdb1 /mnt/backup</tt>
3. Partition & format target VM disk with GParted
4. Mount target root:  <tt>mount /dev/sda1 /mnt/restore</tt>
5. Extract:  <tt>tar -xzpf /mnt/backup/${ARCHIVE_NAME}.tar.gz -C /mnt/restore</tt>
6. Install GRUB:  <tt>grub-install --root-directory=/mnt/restore /dev/sda</tt>"

    zenity --info \
        --title="$TOOL_NAME — Success" \
        --width=640 \
        --text="$REPORT" 2>/dev/null

    log "All done. Archive: $ARCHIVE_PATH ($ARCHIVE_SIZE)"
}

# ── Main ─────────────────────────────────────────────────────

main() {
    log "=== $TOOL_NAME started ==="

    if [[ "$EUID" -ne 0 ]]; then
        zenity --error \
            --title="$TOOL_NAME — Permission Error" \
            --width=480 \
            --text="❌ This tool must be run as <b>root</b>.\n\nOpen a terminal and run:\n<tt>sudo /usr/local/bin/p2v-tool.sh</tt>" 2>/dev/null
        exit 1
    fi

    check_deps
    gather_inputs
    test_ssh
    prepare_destination
    save_metadata
    run_capture
    verify_and_report

    log "=== $TOOL_NAME finished ==="
}

main "$@"
