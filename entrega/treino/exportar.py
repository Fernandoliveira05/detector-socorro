"""
Exporta o modelo treinado para os 3 formatos:
  - socorro.onnx        (entregável da ponderada)
  - socorro_int8.tflite (quantizado)
  - model_data.h        (C array que vai no firmware do ESP32)
Também atualiza feat_norm.h e o model_data.h da pasta firmware.
"""
import subprocess, sys, re
from pathlib import Path
import numpy as np, tensorflow as tf

M = Path("modelos"); SM = M / "socorro_savedmodel"
FW = Path("../firmware/socorro_detector")

# ONNX (a partir do SavedModel)
subprocess.run([sys.executable, "-m", "tf2onnx.convert", "--saved-model", str(SM),
                "--output", str(M/"socorro.onnx"), "--opset", "13"], check=True)

# TFLite int8 (usa o dataset como amostra de calibração)
d = np.load("dataset.npz", allow_pickle=True) if Path("dataset.npz").exists() else None
conv = tf.lite.TFLiteConverter.from_saved_model(str(SM))
conv.optimizations = [tf.lite.Optimize.DEFAULT]
conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
conv.inference_input_type = conv.inference_output_type = tf.int8
if d is not None:
    Xtr = d["Xtr"][..., None].astype(np.float32)
    conv.representative_dataset = lambda: ([Xtr[i:i+1]] for i in range(min(300, len(Xtr))))
tfl = conv.convert(); (M/"socorro_int8.tflite").write_bytes(tfl)

# C array
subprocess.run(f'xxd -i "{M/"socorro_int8.tflite"}" > "{M/"model_data.h"}"', shell=True, check=True)
txt = (M/"model_data.h").read_text()
txt = re.sub(r"unsigned char .*\[\]", "alignas(16) const unsigned char g_socorro_model[]", txt)
txt = re.sub(r"unsigned int .*_len", "const unsigned int g_socorro_model_len", txt)
(M/"model_data.h").write_text("#pragma once\n" + txt)

# sincroniza a pasta do firmware (model_data.h + feat_norm.h)
if FW.exists():
    (FW/"model_data.h").write_text((M/"model_data.h").read_text())
    n = np.load(M/"feat_norm.npz"); mean, std = n["mean"], n["std"]
    (FW/"feat_norm.h").write_text("#pragma once\n" +
        f"static const float MFCC_MEAN[{len(mean)}]={{{','.join(f'{v:.6f}f' for v in mean)}}};\n" +
        f"static const float MFCC_STD[{len(std)}]={{{','.join(f'{v:.6f}f' for v in std)}}};\n")
print("exportado: socorro.onnx, socorro_int8.tflite, model_data.h (+ firmware sincronizado)")
