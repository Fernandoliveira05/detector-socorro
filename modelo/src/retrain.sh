#!/bin/bash
# Reconstrói o dataset, retreina e reexporta (ONNX + TFLite + C array).
cd "$(dirname "$0")/../.." || exit 1
source _work/venv/bin/activate
echo "== 1/3 dataset ==" && python projeto/src/04_build_dataset.py 2>&1 | grep -vE "NotOpenSSL|warnings.warn" | tail -3
echo "== 2/3 treino  ==" && python projeto/src/05_train.py 2>&1 | grep -E "== |precisão|recall|thr_f1=" | grep -vE "NotOpenSSL"
echo "== 3/3 export  ==" && python projeto/src/06_export.py 2>&1 | grep -E "ONNX salvo|máx|TFLite|C array"
