"""
Treina o detector de "socorro": monta as features (MFCC), aplica aumentos,
treina uma CNN pequena e salva o modelo. Rode 'preparar_dados.py' antes.

Ideias-chave:
- normalização GLOBAL fixa das features (probabilidades estáveis);
- aumentos leves + pitch SIMÉTRICO (positivos e negativos) p/ robustez a tom;
- label smoothing + weight decay p/ calibrar a saída;
- split por ARQUIVO (variações de um áudio nunca caem em treino e teste juntas).
"""
import random
from pathlib import Path
import numpy as np, librosa, tensorflow as tf
from tensorflow.keras import layers
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score, precision_recall_curve
from common import SR, CLIP_LEN, N_FRAMES, N_MFCC, fix_length, mfcc, _mfcc_raw

DS = Path("dataset"); M = Path("modelos"); M.mkdir(exist_ok=True)
N_PER_CLASS = 5000
rng = random.Random(7); nprng = np.random.default_rng(7)
tf.random.set_seed(7); np.random.seed(7)

def load(f): return fix_length(librosa.load(f, sr=SR, mono=True)[0])

def augment(y, is_neg=False):
    y = np.roll(y, nprng.integers(-SR//7, SR//7))
    if rng.random() < 0.6:                       # pitch simétrico (± 3 semitons)
        y = librosa.effects.pitch_shift(y=y, sr=SR, n_steps=nprng.uniform(-3, 3))
    if rng.random() < 0.5:
        y = fix_length(librosa.effects.time_stretch(y=y, rate=nprng.uniform(0.8, 1.2)))
    y = y * nprng.uniform(0.5, 1.3)
    m = np.max(np.abs(y)) or 1.0
    return fix_length(y/m if m > 1 else y)

def split(files, seed):
    fs = files[:]; random.Random(seed).shuffle(fs)
    n = len(fs); a, b = int(.7*n), int(.85*n)
    return fs[:a], fs[a:b], fs[b:]

def feats_real(fs): return np.stack([mfcc(load(f)) for f in fs]) if fs else np.empty((0, N_FRAMES, N_MFCC))
def feats_aug(fs, n, is_neg):
    base = [load(f) for f in fs]
    return np.stack([mfcc(base[i] if i < len(base) else augment(rng.choice(base), is_neg)) for i in range(n)])

def specaug(x, training=None):
    if not training: return x
    T, F = tf.shape(x)[1], tf.shape(x)[2]
    for _ in range(2):
        w = tf.random.uniform([], 0, 8, tf.int32); s = tf.random.uniform([], 0, tf.maximum(1, T-w), tf.int32)
        x = x * tf.concat([tf.ones([s]), tf.zeros([w]), tf.ones([T-s-w])], 0)[None, :, None, None]
    return x

def build_model():
    L2 = tf.keras.regularizers.l2(1e-4)
    inp = tf.keras.Input((N_FRAMES, N_MFCC, 1), name="mfcc")
    x = layers.Lambda(lambda t: specaug(t, tf.keras.backend.learning_phase()))(inp)
    for f in (16, 32, 48):
        x = layers.Conv2D(f, 3, padding="same", activation="relu", kernel_regularizer=L2)(x)
        x = layers.BatchNormalization()(x)
        if f < 48: x = layers.MaxPool2D()(x)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dense(48, activation="relu", kernel_regularizer=L2)(x)
    x = layers.Dropout(0.3)(x)
    return tf.keras.Model(inp, layers.Dense(2, activation="softmax", name="prob")(x))

def main():
    pos = sorted(DS.glob("positives/*.wav")) + sorted(DS.glob("positives_variacoes/*.wav"))
    neg = [f for s in ("negatives/fala", "negatives/ruido", "negatives_variacoes")
           for f in sorted((DS/s).glob("*.wav"))]
    ptr, pva, pte = split(pos, 1); ntr, nva, nte = split(neg, 2)

    # normalização global a partir do treino (sem vazamento)
    allm = np.concatenate([_mfcc_raw(load(f)) for f in ptr + ntr], axis=0)
    np.savez(M/"feat_norm.npz", mean=allm.mean(0).astype(np.float32), std=(allm.std(0)+1e-6).astype(np.float32))
    import common; common._norm = None                    # recarrega as stats

    Xtr = np.concatenate([feats_aug(ptr, N_PER_CLASS, False), feats_aug(ntr, N_PER_CLASS, True)])[..., None]
    ytr = np.array([1]*N_PER_CLASS + [0]*N_PER_CLASS)
    Xva = np.concatenate([feats_real(pva), feats_real(nva)])[..., None]
    yva = np.array([1]*len(pva) + [0]*len(nva))
    Xte = np.concatenate([feats_real(pte), feats_real(nte)])[..., None]
    yte = np.array([1]*len(pte) + [0]*len(nte))

    m = build_model()
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.1), metrics=["accuracy"])
    m.fit(Xtr, tf.keras.utils.to_categorical(ytr, 2),
          validation_data=(Xva, tf.keras.utils.to_categorical(yva, 2)),
          epochs=80, batch_size=64, verbose=2,
          callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True)])

    p = m.predict(Xte, verbose=0)[:, 1]
    pr, rc, f1, _ = precision_recall_fscore_support(yte, (p >= .5).astype(int), average="binary", zero_division=0)
    print(f"TESTE: precisão={pr:.3f} recall={rc:.3f} f1={f1:.3f} auc={roc_auc_score(yte, p):.3f}")
    m.save(M/"socorro.keras"); m.export(M/"socorro_savedmodel")
    print("modelo salvo em modelos/ — rode exportar.py para gerar .onnx/.tflite/C")

if __name__ == "__main__":
    main()
