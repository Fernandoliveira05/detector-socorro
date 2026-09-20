// ============================================================================
// features.h — extração de RMS e MFCC no dispositivo (espelha common.py).
// ============================================================================
#pragma once
#include "config.h"

// Calcula o RMS de um bloco (usado no gate de energia — feature do enunciado).
float compute_rms(const float* x, int n);

// Extrai MFCC de uma janela de CLIP_LEN amostras (float, -1..1).
// Escreve N_FRAMES*N_MFCC floats em out (layout [frame][coef]), já normalizado
// (pico->0.95 antes, e média/desvio por-utterance depois), igual ao treino.
void compute_mfcc(const float* clip, float* out);

// Inicializa tabelas (mel filterbank, janela de Hann, DCT). Chamar 1x no setup.
void features_init();
