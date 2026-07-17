package com.cybel.facebridge;

import android.graphics.Bitmap;
import android.graphics.PointF;
import android.media.FaceDetector;
import android.media.Image;

import java.nio.ByteBuffer;

/**
 * Conversions caméra headless : Camera2 livre du YUV_420_888, mais
 * android.media.FaceDetector n'accepte qu'un Bitmap.Config.RGB_565 — il n'existe
 * pas de chemin direct, d'où la conversion manuelle NV21 -> RGB565 ci-dessous
 * (plutôt qu'un aller-retour YuvImage.compressToJpeg/BitmapFactory.decode, inutilement
 * coûteux sur ce matériel).
 */
final class ImageConversions {

    private ImageConversions() {
    }

    static byte[] yuv420ToNv21(Image image) {
        int width = image.getWidth();
        int height = image.getHeight();
        byte[] nv21 = new byte[width * height * 3 / 2];

        Image.Plane[] planes = image.getPlanes();
        ByteBuffer yBuffer = planes[0].getBuffer();
        int yRowStride = planes[0].getRowStride();
        int yPixelStride = planes[0].getPixelStride();

        int pos = 0;
        if (yRowStride == width && yPixelStride == 1) {
            yBuffer.get(nv21, 0, width * height);
            pos = width * height;
        } else {
            byte[] row = new byte[yRowStride];
            for (int r = 0; r < height; r++) {
                yBuffer.position(r * yRowStride);
                int rowLen = Math.min(yRowStride, yBuffer.remaining());
                yBuffer.get(row, 0, rowLen);
                for (int c = 0; c < width; c++) {
                    nv21[pos++] = row[c * yPixelStride];
                }
            }
        }

        // NV21 = Y plein résolution puis V,U entrelacés (dans cet ordre) à demi résolution.
        ByteBuffer uBuffer = planes[1].getBuffer();
        ByteBuffer vBuffer = planes[2].getBuffer();
        int uRowStride = planes[1].getRowStride();
        int uPixelStride = planes[1].getPixelStride();
        int vRowStride = planes[2].getRowStride();
        int vPixelStride = planes[2].getPixelStride();

        int chromaWidth = width / 2;
        int chromaHeight = height / 2;
        byte[] uRow = new byte[uRowStride];
        byte[] vRow = new byte[vRowStride];
        for (int r = 0; r < chromaHeight; r++) {
            vBuffer.position(r * vRowStride);
            vBuffer.get(vRow, 0, Math.min(vRowStride, vBuffer.remaining()));
            uBuffer.position(r * uRowStride);
            uBuffer.get(uRow, 0, Math.min(uRowStride, uBuffer.remaining()));
            for (int c = 0; c < chromaWidth; c++) {
                nv21[pos++] = vRow[c * vPixelStride];
                nv21[pos++] = uRow[c * uPixelStride];
            }
        }
        return nv21;
    }

    static Bitmap nv21ToRgb565(byte[] nv21, int width, int height) {
        int frameSize = width * height;
        int[] pixels = new int[frameSize];
        for (int j = 0; j < height; j++) {
            int yBase = j * width;
            int uvBase = frameSize + (j >> 1) * width;
            for (int i = 0; i < width; i++) {
                int y = 0xff & nv21[yBase + i];
                int uvOffset = uvBase + (i & ~1);
                int v = (0xff & nv21[uvOffset]) - 128;
                int u = (0xff & nv21[uvOffset + 1]) - 128;

                int r = clamp((int) (y + 1.402f * v));
                int g = clamp((int) (y - 0.344f * u - 0.714f * v));
                int b = clamp((int) (y + 1.772f * u));

                pixels[yBase + i] = 0xff000000 | (r << 16) | (g << 8) | b;
            }
        }
        // Bitmap.createBitmap(int[], ...) attend des couleurs ARGB_8888 en entrée quel que
        // soit le Config cible — Android se charge de la conversion vers RGB_565.
        return Bitmap.createBitmap(pixels, width, height, Bitmap.Config.RGB_565);
    }

    /**
     * FaceDetector.Face n'expose pas de rectangle : seulement le point médian des yeux
     * et leur distance. Le facteur de cadrage ci-dessous est une heuristique à ajuster
     * après observation sur la caméra réelle (voir README.md).
     */
    static Bitmap cropFaceRegion(Bitmap frame, FaceDetector.Face face, int targetSize) {
        PointF midPoint = new PointF();
        face.getMidPoint(midPoint);
        float eyesDistance = face.eyesDistance();

        float boxWidth = eyesDistance * 2.2f;
        float boxHeight = eyesDistance * 2.8f;
        float centerX = midPoint.x;
        float centerY = midPoint.y + eyesDistance * 0.6f;

        int left = clampInt((int) (centerX - boxWidth / 2f), 0, frame.getWidth() - 1);
        int top = clampInt((int) (centerY - boxHeight / 2f), 0, frame.getHeight() - 1);
        int right = clampInt((int) (centerX + boxWidth / 2f), left + 1, frame.getWidth());
        int bottom = clampInt((int) (centerY + boxHeight / 2f), top + 1, frame.getHeight());

        Bitmap cropped = Bitmap.createBitmap(frame, left, top, right - left, bottom - top);
        return Bitmap.createScaledBitmap(cropped, targetSize, targetSize, true);
    }

    private static int clamp(int value) {
        return value < 0 ? 0 : Math.min(value, 255);
    }

    private static int clampInt(int value, int min, int max) {
        return Math.max(min, Math.min(value, max));
    }
}
