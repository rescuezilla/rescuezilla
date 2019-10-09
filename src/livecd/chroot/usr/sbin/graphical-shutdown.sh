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

yad --center \
    --width 300 \
    --title "End Session" \
    --image=gnome-shutdown \
    --button="Cancel:0" \
    --button="Shutdown:1" \
    --button="Reboot:2" \
    --text "Choose action."

ret=$?

[[ $ret -eq 0 ]] && exit 0
[[ $ret -eq 1 ]] && sudo /sbin/poweroff
[[ $ret -eq 2 ]] && sudo /sbin/reboot
