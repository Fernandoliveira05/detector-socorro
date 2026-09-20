import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import N_FRAMES, N_MFCC
import tensorflow as tf
from tensorflow.keras import layers
from sklearn.metrics import (confusion_matrix, precision_recall_fscore_support,
                             roc_auc_score, precision_recall_curve)

PROJ = Path(__file__).resolve().parents[1]
tf.random.set_seed(7); np.random.seed(7)

d = np.load(PROJ / "metadata" / "dataset.npz", allow_pickle=True)
Xtr, ytr, Xva, yva, Xte, yte = (d[k] for k in ["Xtr","ytr","Xva","yva","Xte","yte"])
te_files = d["te_files"]
Xtr = Xtr[..., None]; Xva = Xva[..., None]; Xte = Xte[..., None]


class SpecAugment(layers.Layer):
    """Mascara faixas de tempo e frequência (só durante o treino)."""
    def __init__(self, t_mask=8, f_mask=4, n=2, **kw):
        super().__init__(**kw); self.t, self.f, self.n = t_mask, f_mask, n
    def call(self, x, training=None):
        if not training:
            return x
        T, F = tf.shape(x)[1], tf.shape(x)[2]
        for _ in range(self.n):
            # máscara de tempo
            w = tf.random.uniform([], 0, self.t, tf.int32)
            s = tf.random.uniform([], 0, tf.maximum(1, T-w), tf.int32)
            mt = tf.concat([tf.ones([s]), tf.zeros([w]), tf.ones([T-s-w])], 0)
            x = x * mt[None, :, None, None]
            # máscara de frequência
            w = tf.random.uniform([], 0, self.f, tf.int32)
            s = tf.random.uniform([], 0, tf.maximum(1, F-w), tf.int32)
            mf = tf.concat([tf.ones([s]), tf.zeros([w]), tf.ones([F-s-w])], 0)
            x = x * mf[None, None, :, None]
        return x


L2 = tf.keras.regularizers.l2(1e-4)          # weight decay: reduz overfitting

def build():
    inp = tf.keras.Input((N_FRAMES, N_MFCC, 1), name="mfcc")
    x = SpecAugment(name="specaugment")(inp)
    x = layers.Conv2D(16, 3, padding="same", activation="relu", kernel_regularizer=L2)(x)
    x = layers.BatchNormalization()(x); x = layers.MaxPool2D()(x)
    x = layers.Conv2D(32, 3, padding="same", activation="relu", kernel_regularizer=L2)(x)
    x = layers.BatchNormalization()(x); x = layers.MaxPool2D()(x)
    x = layers.Conv2D(48, 3, padding="same", activation="relu", kernel_regularizer=L2)(x)
    x = layers.BatchNormalization()(x)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dense(48, activation="relu", kernel_regularizer=L2)(x)
    x = layers.Dropout(0.3)(x)
    out = layers.Dense(2, activation="softmax", name="prob")(x)
    return tf.keras.Model(inp, out)

model = build()
# label smoothing 0.1: evita softmax saturar em 0/1 -> probabilidades calibradas/estáveis
model.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.1),
              metrics=["accuracy"])
model.summary()

cb = [tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12,
                                       restore_best_weights=True),
      tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", patience=5, factor=0.5)]
# one-hot p/ o label smoothing (CategoricalCrossentropy)
ytr_oh = tf.keras.utils.to_categorical(ytr, 2)
yva_oh = tf.keras.utils.to_categorical(yva, 2)
model.fit(Xtr, ytr_oh, validation_data=(Xva, yva_oh), epochs=80, batch_size=64,
          callbacks=cb, verbose=2)

def evaluate(X, y, name, thr):
    p = model.predict(X, verbose=0)[:, 1]
    yhat = (p >= thr).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(y, yhat, average="binary", zero_division=0)
    cm = confusion_matrix(y, yhat)
    auc = roc_auc_score(y, p) if len(set(y)) > 1 else float("nan")
    print(f"\n== {name} (thr={thr:.3f}) ==")
    print(f"  precisão={pr:.3f}  recall={rc:.3f}  f1={f1:.3f}  auc={auc:.3f}")
    print(f"  confusão [[TN FP][FN TP]]:\n{cm}")
    return dict(precision=float(pr), recall=float(rc), f1=float(f1), auc=float(auc),
                confusion=cm.tolist(), threshold=float(thr)), p, yhat

# thresholds a partir da VALIDAÇÃO
pv = model.predict(Xva, verbose=0)[:, 1]
prec, rec, thrs = precision_recall_curve(yva, pv)
prec, rec = prec[:-1], rec[:-1]
f1s = 2*prec*rec/(prec+rec+1e-9)
thr_f1 = float(thrs[np.argmax(f1s)])
# recall-first: menor threshold com recall>=0.95 (maior precisão possível)
ok = np.where(rec >= 0.95)[0]
thr_recall = float(thrs[ok[np.argmax(prec[ok])]]) if len(ok) else thr_f1
# balanceado (default do demo): maior recall com precisão>=0.92
okp = np.where(prec >= 0.92)[0]
thr_precision = float(thrs[okp[np.argmax(rec[okp])]]) if len(okp) else thr_f1

m_val, _, _ = evaluate(Xva, yva, "VALIDAÇÃO", thr_f1)
m_test_f1, _, _ = evaluate(Xte, yte, "TESTE (thr F1)", thr_f1)
m_test_prec, _, _ = evaluate(Xte, yte, "TESTE (thr balanceado)", thr_precision)
m_test_rec, p_te, yhat_te = evaluate(Xte, yte, "TESTE (thr recall-first)", thr_recall)

# diagnóstico: erros no teste
print("\n== ERROS NO TESTE (thr recall-first) ==")
for i, f in enumerate(te_files):
    if yhat_te[i] != yte[i]:
        tipo = "FN (perdeu socorro)" if yte[i] == 1 else "FP (falso alarme)"
        print(f"  {tipo}  p={p_te[i]:.2f}  {Path(f).name}")

metrics = {"val": m_val, "test_thr_f1": m_test_f1, "test_balanced": m_test_prec,
           "test_recall_first": m_test_rec, "thr_f1": thr_f1,
           "thr_recall_first": thr_recall, "thr_balanced": thr_precision}
# preserva o ponto de operação congelado (frozen) entre treinos
_mpath = PROJ / "models" / "metrics.json"
if _mpath.exists():
    _old = json.load(open(_mpath))
    if "frozen" in _old:
        metrics["frozen"] = _old["frozen"]
(PROJ / "models").mkdir(exist_ok=True)
model.save(PROJ / "models" / "socorro.keras")
model.export(PROJ / "models" / "socorro_savedmodel")
json.dump(metrics, open(PROJ / "models" / "metrics.json", "w"), indent=2, ensure_ascii=False)
print(f"\nthr_f1={thr_f1:.3f}  thr_recall_first={thr_recall:.3f}")
print("modelos salvos em projeto/models/")
