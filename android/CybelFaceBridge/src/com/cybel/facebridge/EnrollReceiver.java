package com.cybel.facebridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Déclenché par le personnel via `am broadcast` (scripts/termux/enroll_visitor.sh),
 * jamais automatiquement — pas de capture silencieuse d'un visiteur non consentant.
 */
public class EnrollReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        String name = intent.getStringExtra("name");
        if (name == null || name.trim().isEmpty()) {
            return;
        }
        String civility = intent.getStringExtra("civility");

        Intent service = new Intent(context, FaceRecognitionService.class);
        service.setAction(FaceRecognitionService.ACTION_ENROLL);
        service.putExtra("name", name.trim());
        service.putExtra("civility", civility == null ? "" : civility);
        context.startService(service);
    }
}
