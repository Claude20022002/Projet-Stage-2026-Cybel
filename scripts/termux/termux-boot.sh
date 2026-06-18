#!/data/data/com.termux/files/usr/bin/bash
# Relance CYBEL au démarrage de Termux (nécessite termux-boot).
sleep 15
bash "${CYBEL_HOME:-$HOME/cybel}/scripts/termux/start_cybel.sh" >>"$HOME/cybel-boot.log" 2>&1
