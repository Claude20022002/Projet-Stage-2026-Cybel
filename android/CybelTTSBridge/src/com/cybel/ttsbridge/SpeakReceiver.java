package com.cybel.ttsbridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class SpeakReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        String text = intent.getStringExtra("text");
        if (text == null || text.length() == 0) {
            return;
        }
        String lang = intent.getStringExtra("lang");
        Intent service = new Intent(context, SpeakService.class);
        service.putExtra("text", text);
        service.putExtra("lang", lang);
        context.startService(service);
    }
}
