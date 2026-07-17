#!/system/bin/sh
B=/data/data/com.termux/files/usr/bin/bash
P=/data/data/com.termux/files/usr/bin
H=/data/data/com.termux/files/home
export PATH=$P:/system/bin
for f in $H/cybel/scripts/termux/*.sh $H/cybel-test/scripts/termux/*.sh; do
  su -c "sed -i 's/\r$//' $f"
done
su -c "HOME=$H PATH=$P:/system/bin $B $H/cybel/scripts/termux/stop_cybel.sh"
su -c "HOME=$H PATH=$P:/system/bin CYBEL_HOME=$H/cybel $B $H/cybel/scripts/termux/start_cybel.sh" || true
su -c "HOME=$H PATH=$P:/system/bin $B $H/cybel-test/scripts/termux/stop_cybel_test.sh"
su -c "HOME=$H PATH=$P:/system/bin CYBEL_HOME=$H/cybel-test BACKEND_PORT=8001 $B $H/cybel-test/scripts/termux/start_cybel_test.sh" || true
