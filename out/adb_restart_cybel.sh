#!/system/bin/sh
B=/data/data/com.termux/files/usr/bin/bash
H=/data/data/com.termux/files/home
for f in $H/cybel/scripts/termux/*.sh $H/cybel-test/scripts/termux/*.sh; do
  su -c "sed -i 's/\r$//' $f"
done
su -c "HOME=$H $B $H/cybel/scripts/termux/stop_cybel.sh"
su -c "HOME=$H CYBEL_HOME=$H/cybel $B $H/cybel/scripts/termux/start_cybel.sh"
su -c "HOME=$H $B $H/cybel-test/scripts/termux/stop_cybel_test.sh"
su -c "HOME=$H CYBEL_HOME=$H/cybel-test BACKEND_PORT=8001 $B $H/cybel-test/scripts/termux/start_cybel_test.sh"
