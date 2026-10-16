package com.cybel.secondscreen;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/** Réaffiche le dernier visuel sur l'écran du dessous après un redémarrage du robot. */
public class BootReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }
        Log.i(SecondScreenService.TAG, "Boot — démarrage de l'affichage écran du dessous");
        context.startService(new Intent(context, SecondScreenService.class));
    }
}
