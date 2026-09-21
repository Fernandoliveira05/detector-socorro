// ============================================================================
// features.h — extração de RMS e MFCC no dispositivo (espelha common.py).
// ============================================================================
#pragma once
#include <stdint.h>      // int16_t
#include "config.h"

// Lêem a janela de 1 s DIRETO do buffer circular (ring), terminando em end_idx
// (= writeIdx). Assim não precisamos de um segundo buffer de 1 s (economia de RAM).

// RMS (0..1) da janela — usado no gate de energia (feature do enunciado).
float compute_rms(const int16_t* ring, int end_idx);

// MFCC da janela -> N_FRAMES*N_MFCC floats em out, normalizado (pico->0.95 +
// estatísticas globais do treino em feat_norm.h), igual ao treino.
void compute_mfcc(const int16_t* ring, int end_idx, float* out);

// Inicializa tabelas (mel filterbank, janela de Hann, DCT). Chamar 1x no setup.
void features_init();
