#!/usr/bin/env python3
"""
Etapa 6: exporta o modelo treinado para:
  - socorro.onnx        (entregável da ponderada)
  - socorro_int8.tflite (quantizado, p/ ESP32 / TFLite Micro)
  - socorro_model_data.h (C array p/ firmware)
Valida a paridade Keras vs ONNX.
"""
import sys, subprocess
from pathlib import Path
import numpy as np, tensorflow as tf, onnx, onnxruntime as ort
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import N_FRAMES, N_MFCC

PROJ = Path(__file__).resolve().parents[1]
M = PROJ / "models"
SM = M / "socorro_savedmodel"       # SavedModel (não depende da camada custom)

# ---------- ONNX (a partir do SavedModel) ----------
onnx_path = M / "socorro.onnx"
subprocess.run([sys.executable, "-m", "tf2onnx.convert",
                "--saved-model", str(SM), "--output", str(onnx_path),
                "--opset", "13"], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("ONNX salvo:", onnx_path.name)

# paridade: SavedModel vs ONNX
d = np.load(PROJ / "metadata" / "dataset.npz", allow_pickle=True)
xt = d["Xte"][:32, ..., None].astype(np.float32)
sm = tf.saved_model.load(str(SM))
serve = sm.signatures["serve"]
sm_out = serve(mfcc=tf.constant(xt))
sm_out = list(sm_out.values())[0].numpy()
sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
in_name = sess.get_inputs()[0].name
onnx_out = sess.run(None, {in_name: xt})[0]
print("máx |SavedModel-ONNX| =", float(np.max(np.abs(sm_out - onnx_out))))

# ---------- TFLite int8 ----------
def rep():
    Xtr = d["Xtr"][..., None].astype(np.float32)
    for i in range(0, min(300, len(Xtr))):
        yield [Xtr[i:i+1]]
conv = tf.lite.TFLiteConverter.from_saved_model(str(M / "socorro_savedmodel"))
conv.optimizations = [tf.lite.Optimize.DEFAULT]
conv.representative_dataset = rep
conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
conv.inference_input_type = tf.int8
conv.inference_output_type = tf.int8
tfl = conv.convert()
tfl_path = M / "socorro_int8.tflite"
tfl_path.write_bytes(tfl)
print(f"TFLite int8 salvo: {tfl_path.name} ({len(tfl)/1024:.1f} KB)")

# ---------- C array ----------
h_path = M / "socorro_model_data.h"
subprocess.run(f'xxd -i "{tfl_path}" > "{h_path}"', shell=True, check=True)
# renomeia símbolos p/ nomes limpos
txt = h_path.read_text()
import re
txt = re.sub(r"unsigned char .*\[\]", "alignas(16) const unsigned char g_socorro_model[]", txt)
txt = re.sub(r"unsigned int .*_len", "const unsigned int g_socorro_model_len", txt)
h_path.write_text("// Modelo socorro quantizado int8 (gerado)\n#pragma once\n" + txt)
print("C array salvo:", h_path.name)

# ---------- sincroniza a pasta esp32/ (firmware) ----------
esp = PROJ.parent / "esp32"
if esp.exists():
    import shutil
    shutil.copy(h_path, esp / "model_data.h")
    fn = PROJ / "models" / "feat_norm.npz"
    if fn.exists():
        dnorm = np.load(fn); mean, std = dnorm["mean"], dnorm["std"]
        (esp / "feat_norm.h").write_text(
            "// Estatísticas GLOBAIS de normalização do MFCC (geradas do treino).\n#pragma once\n"
            f"static const float MFCC_MEAN[{len(mean)}] = {{{', '.join(f'{v:.6f}f' for v in mean)}}};\n"
            f"static const float MFCC_STD[{len(std)}]  = {{{', '.join(f'{v:.6f}f' for v in std)}}};\n")
    print("esp32/ sincronizado (model_data.h + feat_norm.h)")
