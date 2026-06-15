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
        Intent service = new Intent(context, SpeakService.class);
        service.putExtra("text", text);
        context.startService(service);
    }
}
