#!/system/bin/sh
B=/data/data/com.termux/files/usr/bin/bash
H=/data/data/com.termux/files/home
su -c "$B $H/cybel/scripts/termux/stop_cybel.sh"
su -c "$B $H/cybel/scripts/termux/start_cybel.sh"
su -c "$B $H/cybel-test/scripts/termux/stop_cybel_test.sh"
su -c "$B $H/cybel-test/scripts/termux/start_cybel_test.sh"
