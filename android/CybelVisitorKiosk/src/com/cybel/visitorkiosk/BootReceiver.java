package com.cybel.visitorkiosk;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }
        BackendStarter.ensureRunning(context, new BackendStarter.Callback() {
            @Override
            public void onReady() {
                launchKiosk(context);
            }

            @Override
            public void onFailed(String message) {
                launchKiosk(context);
            }
        });
    }

    private static void launchKiosk(Context context) {
        Intent launch = new Intent(context, MainActivity.class);
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(launch);
    }
}
