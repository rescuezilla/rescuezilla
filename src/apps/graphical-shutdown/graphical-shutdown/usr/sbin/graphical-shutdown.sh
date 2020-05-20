#! /bin/bash
#
# Lightweight graphical shutdown script. Uses 'yad' ("Yet Another Dialog") for
# graphical GTK+ popups.
#
# Adapted ideas from [1] [2]. Man-page at [3].
#
# [1] https://askubuntu.com/questions/737035/ask-for-user-confirmation-before-executing-a-script
# [2] https://sourceforge.net/p/yad-dialog/wiki/Examples/
# [3] https://www.systutorials.com/docs/linux/man/1-yad/

end_session=$(gettext "graphical-shutdown" "End Session")
cancel=$(gettext "graphical-shutdown" "Cancel")
shutdown=$(gettext "graphical-shutdown" "Shutdown")
reboot=$(gettext "graphical-shutdown" "Reboot")
choose_action=$(gettext "graphical-shutdown" "Choose action.")

yad --center \
    --width 300 \
    --title="$end_session" \
    --image=gnome-shutdown \
    --button="$cancel:0" \
    --button="$shutdown:1" \
    --button="$reboot:2" \
    --text "$choose_action"

ret=$?

[[ $ret -eq 0 ]] && exit 0
[[ $ret -eq 1 ]] && sudo /sbin/poweroff
[[ $ret -eq 2 ]] && sudo /sbin/reboot
