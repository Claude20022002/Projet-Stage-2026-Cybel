package com.cybel.facebridge;

import android.content.Context;
import android.graphics.Bitmap;
import android.util.Log;

import org.json.JSONObject;
import org.tensorflow.lite.Interpreter;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Charge assets/face_embedding.tflite (fourni par l'utilisateur — voir README.md,
 * jamais téléchargé automatiquement par l'outillage) et calcule un embedding de visage.
 *
 * Ne code JAMAIS en dur la forme des tenseurs : les lit dynamiquement sur l'interpréteur
 * plutôt que de supposer une convention MobileFaceNet particulière, puisque le modèle
 * est un asset interchangeable.
 */
public class FaceEmbedder {
    private static final String TAG = "CybelFaceEmbedder";
    private static final String MODEL_ASSET = "face_embedding.tflite";
    private static final String CONFIG_ASSET = "face_embedding_config.json";

    private final Interpreter interpreter;
    private final int inputSize;
    private final int outputDim;
    private final float mean;
    private final float std;
    private final boolean quantized;
    private final boolean l2Normalize;

    public FaceEmbedder(Context context) throws IOException {
        File modelFile = copyAssetToFiles(context, MODEL_ASSET);
        JSONObject config = readConfigJson(context);

        try {
            interpreter = new Interpreter(modelFile, new Interpreter.Options().setNumThreads(2));
        } catch (Exception e) {
            throw new IOException("Impossible de charger " + MODEL_ASSET + " : " + e.getMessage(), e);
        }

        int[] inputShape = interpreter.getInputTensor(0).shape();
        int[] outputShape = interpreter.getOutputTensor(0).shape();

        this.inputSize = inputShape.length >= 2 ? inputShape[1] : config.optInt("input_size", 112);
        this.outputDim = outputShape[outputShape.length - 1];
        this.mean = (float) config.optDouble("mean", 127.5);
        this.std = (float) config.optDouble("std", 127.5);
        this.quantized = config.optBoolean("quantized", false);
        this.l2Normalize = config.optBoolean("l2_normalize", true);

        Log.i(TAG, "Modèle chargé : input=" + inputSize + "x" + inputSize
                + " output_dim=" + outputDim + " quantized=" + quantized);
    }

    /** Calcule l'embedding d'un visage déjà cadré (voir ImageConversions.cropFaceRegion). */
    public float[] embed(Bitmap faceCrop) {
        Bitmap resized = Bitmap.createScaledBitmap(faceCrop, inputSize, inputSize, true);
        ByteBuffer input = ByteBuffer.allocateDirect(
                inputSize * inputSize * 3 * (quantized ? 1 : 4));
        input.order(ByteOrder.nativeOrder());

        int[] pixels = new int[inputSize * inputSize];
        resized.getPixels(pixels, 0, inputSize, 0, 0, inputSize, inputSize);
        for (int pixel : pixels) {
            float r = (pixel >> 16) & 0xFF;
            float g = (pixel >> 8) & 0xFF;
            float b = pixel & 0xFF;
            if (quantized) {
                input.put((byte) r);
                input.put((byte) g);
                input.put((byte) b);
            } else {
                input.putFloat((r - mean) / std);
                input.putFloat((g - mean) / std);
                input.putFloat((b - mean) / std);
            }
        }
        input.rewind();

        float[][] output = new float[1][outputDim];
        interpreter.run(input, output);
        float[] embedding = output[0];

        if (l2Normalize) {
            double norm = 0.0;
            for (float v : embedding) {
                norm += (double) v * v;
            }
            norm = Math.sqrt(norm);
            if (norm > 1e-6) {
                for (int i = 0; i < embedding.length; i++) {
                    embedding[i] = (float) (embedding[i] / norm);
                }
            }
        }
        return embedding;
    }

    public void close() {
        interpreter.close();
    }

    private static File copyAssetToFiles(Context context, String assetName) throws IOException {
        File outFile = new File(context.getFilesDir(), assetName);
        try (InputStream in = context.getAssets().open(assetName);
             OutputStream out = new FileOutputStream(outFile)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
        }
        return outFile;
    }

    private static JSONObject readConfigJson(Context context) throws IOException {
        try (InputStream in = context.getAssets().open(CONFIG_ASSET)) {
            java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int read;
            while ((read = in.read(buffer)) != -1) {
                bos.write(buffer, 0, read);
            }
            return new JSONObject(bos.toString("UTF-8"));
        } catch (Exception e) {
            throw new IOException("Impossible de lire " + CONFIG_ASSET, e);
        }
    }
}
