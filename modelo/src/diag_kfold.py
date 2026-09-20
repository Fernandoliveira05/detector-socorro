#!/usr/bin/env python3
"""
Diagnóstico: k-fold CV do setup atual (features+modelo) pra estimar o TETO real
de desempenho e a VARIÂNCIA (um único split engana com pouco dado). Também faz
análise de erros: quais clipes reais são mais difíceis.

Roda com dados REAIS (sem augmentation na validação) e treina 1 modelo por fold
com augmentation leve no treino. Não altera o modelo de produção.
"""
import sys, importlib.util
from pathlib import Path
import numpy as np, tensorflow as tf
from tensorflow.keras import layers
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, f1_score, precision_recall_fscore_support

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
from common import N_FRAMES, N_MFCC, SR, fix_length, mfcc
import librosa

# importa funções do 04 (nome numérico -> importlib)
spec = importlib.util.spec_from_file_location("build", SRC / "04_build_dataset.py")
build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)

def load_real(files):
    return np.stack([mfcc(build.load(f)) for f in files])

def make_model():
    inp = tf.keras.Input((N_FRAMES, N_MFCC, 1))
    x = layers.Conv2D(16,3,padding="same",activation="relu")(inp)
    x = layers.BatchNormalization()(x); x = layers.MaxPool2D()(x)
    x = layers.Conv2D(32,3,padding="same",activation="relu")(x)
    x = layers.BatchNormalization()(x); x = layers.MaxPool2D()(x)
    x = layers.Conv2D(48,3,padding="same",activation="relu")(x)
    x = layers.BatchNormalization()(x)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dense(48,activation="relu")(x); x = layers.Dropout(0.3)(x)
    out = layers.Dense(2,activation="softmax")(x)
    m = tf.keras.Model(inp,out)
    m.compile(optimizer="adam", loss="sparse_categorical_crossentropy")
    return m

def main():
    pos, neg = build.list_files()
    files = pos + neg
    y = np.array([1]*len(pos) + [0]*len(neg))
    print(f"positivos={len(pos)} negativos={len(neg)}")

    Xreal = load_real(files)[...,None]           # features reais de todos
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)
    aucs, f1s = [], []
    hard = {}
    for k,(tr,te) in enumerate(skf.split(Xreal, y)):
        # augmentation leve no treino: usa as features reais + ruído gaussiano leve
        Xtr, ytr = Xreal[tr], y[tr]
        aug = Xtr + np.random.normal(0,0.1,Xtr.shape).astype(np.float32)
        Xtr2 = np.concatenate([Xtr, aug]); ytr2 = np.concatenate([ytr, ytr])
        m = make_model()
        m.fit(Xtr2, ytr2, epochs=25, batch_size=64, verbose=0,
              class_weight={0:1.0, 1:len(neg)/len(pos)})
        p = m.predict(Xreal[te], verbose=0)[:,1]
        auc = roc_auc_score(y[te], p)
        f1 = f1_score(y[te], (p>=0.5).astype(int))
        aucs.append(auc); f1s.append(f1)
        print(f"  fold {k+1}: AUC={auc:.3f}  F1={f1:.3f}")
        for i,idx in enumerate(te):               # coleta erros
            if (p[i]>=0.5) != (y[idx]==1):
                hard[files[idx].name] = (y[idx], round(float(p[i]),2))
    print(f"\nTETO estimado: AUC={np.mean(aucs):.3f}±{np.std(aucs):.3f}  "
          f"F1={np.mean(f1s):.3f}±{np.std(f1s):.3f}")
    print(f"\nClipes reais MAIS DIFÍCEIS (erros em CV): {len(hard)}")
    for n,(yt,pp) in sorted(hard.items(), key=lambda x:abs(x[1][1]-0.5), reverse=True)[:15]:
        tipo = "FN (socorro perdido)" if yt==1 else "FP (falso alarme)"
        print(f"  {tipo}  p={pp}  {n}")

if __name__ == "__main__":
    main()
