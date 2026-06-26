#!/system/bin/sh
su -c '/data/data/com.termux/files/usr/bin/bash -lc "bash /data/data/com.termux/files/home/cybel/scripts/termux/stop_cybel.sh; bash /data/data/com.termux/files/home/cybel/scripts/termux/start_cybel.sh"'
su -c '/data/data/com.termux/files/usr/bin/bash -lc "bash /data/data/com.termux/files/home/cybel-test/scripts/termux/stop_cybel_test.sh; bash /data/data/com.termux/files/home/cybel-test/scripts/termux/start_cybel_test.sh"'
