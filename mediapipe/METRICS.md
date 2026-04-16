# Descrição das métricas calculadas em `mediapipe/test_mp.py`

Este documento descreve, em linguagem acessível e com fórmulas, todas as métricas que o script `mediapipe/test_mp.py` calcula durante a execução.

> Observação: os nomes das variáveis e parâmetros estão de acordo com o código atual no repositório (abril/2026).

---

## Resumo das métricas

1. Ombros (shoulder)
2. Pescoço lateral (neck_lat)
3. Pescoço frontal / "neck forward" (neck_fwd)
4. Score global (global_score)
5. Percentual de tempo em má postura (pct_bad)

Cada componente produz um score contínuo no intervalo 0..1, onde 1 = postura ideal (bom) e 0 = postura muito ruim.

---

## 1) Ombros (shoulder)

- Pontos usados: landmarks MediaPipe 11 (left_shoulder) e 12 (right_shoulder).
- Pixel coordinates: p_left = (x_l, y_l), p_right = (x_r, y_r) obtidos por `get_pixel(lm[index], fw, fh)`.

- Definição do ângulo:

  - Primeiro calcula-se o ângulo horizontal entre os ombros usando a função:

    angle_raw = atan2(dy, dx) em graus, onde
      dx = x_r - x_l
      dy = y_l - y_r  (repare na orientação usada no código)

  - O ângulo usado para avaliação é o menor entre `|angle_raw|` e `|180 - |angle_raw||`:

    angle = min(|angle_raw|, |180 - |angle_raw||)

    Essa normalização garante que o ângulo esteja sempre no intervalo 0..90 (simetria de 180°).

- Mapeamento para score (0..1):

  - Primeiro aplica-se `angle_to_score(angle, max_angle=20.0)` definida como:

    x = clamp(angle / max_angle, 0, 1)
    score_raw = 1 - x

    Ou seja: se angle = 0° => score_raw = 1.0; se angle >= max_angle (20°) => score_raw = 0.0.

  - Suavização temporal (EMA):

    score = EMA(key='shoulder', value=score_raw, alpha=EMA_ALPHA)

    O EMA (exponential moving average) usado permite estabilidade temporal. `EMA_ALPHA` padrão: 0.25.

- Resultado armazenado em `posture['shoulder'] = (p_left, p_right, score, detail)` (detail no código atual é string do ângulo, mas pode ser ocultado no HUD).

---

## 2) Pescoço lateral (neck_lat)

- Pontos usados: 0 (nose) e ponto `neck` definido como média dos ombros:

  neck = ( (x_l + x_r)/2 , (y_l + y_r)/2 ) em pixels.

- Vetor usado: dx = nose.x - neck.x ; dy = nose.y - neck.y

- Ângulo lateral computado por:

  angle_lat_raw = degrees( atan2(dx, -dy) )
  angle_lat = min(|angle_lat_raw|, |180 - |angle_lat_raw||)

  (mesma normalização usada para ângulos em geral)

- Mapeamento para score:

  score_lat_raw = angle_to_score(angle_lat, max_angle=24.0)
  score_lat = EMA('neck_lat', score_lat_raw)

  max_angle usado = 24° por default.

---

## 3) Pescoço frontal / "neck forward" (neck_fwd)

- Motivação: medir a projeção frontal da cabeça em relação ao pescoço (quão à frente a cabeça está).

- Pontos e medidas:

  - nose (px, py)
  - neck (médio dos ombros) como acima
  - shoulder_width (sw) = distância euclidiana entre ombros = sqrt((x_l-x_r)^2 + (y_l-y_r)^2)
  - dist_nose = distância euclidiana entre nose e neck

- Razão (ratio) usada:

  ratio = dist_nose / shoulder_width

  (proporciona normalização em relação ao tamanho da pessoa no frame)

- Mapear ratio para score raw:

  raw_neck_fwd = clamp( (ratio - 0.25) / 0.40, 0, 1 )

  - INTERPRETAÇÃO: quando ratio <= 0.25 → raw ≈ 0 (muito inclinado para frente);
    quando ratio >= 0.65 -> raw ≈ 1 (posição neutra/ereta). Esses valores (0.25 e 0.65) são parâmetros heurísticos presentes no código.

  - O valor do ratio é também suavizado por EMA: ratio = EMA('neck_fwd_ratio', ratio)
  - Em seguida aplica-se EMA no raw: score_fwd = EMA('neck_fwd', raw_neck_fwd)

- Score final do pescoço no código:

  score_neck = min(score_lat, score_fwd)

  Ou seja, a avaliação final do pescoço é conservadora — a pior das duas componentes (lateral e frontal) domina.

---

## 4) Score global (global_score)

- Definição:

  Se `posture` não está vazio:

    global_score = mean( score_i for cada componente i em posture )

  Caso contrário, assume-se `global_score = 1.0` (bom).

- Os componentes presentes no `posture` atualmente são: `shoulder` e `neck`.

---

## 5) Percentual de tempo em má postura (pct_bad)

- Para cada frame o script avalia se `global_score < BAD_POSTURE_THRESHOLD` (threshold padrão = 0.45).

- Esse booleano (True=bad) é empurrado para um deque `_posture_history` com tamanho `POSTURE_WINDOW = POSTURE_WINDOW_SEC * FPS_ESTIMATE` (padrão 30s * 30fps = 900 frames).

- pct_bad = sum(_posture_history) / len(_posture_history)

  Ou seja, percentagem de frames na janela (ex.: 30s) em que a postura era considerada ruim.

---

## Suavização temporal (EMA)

- Implementação:

  EMA(key, value, alpha) mantém um estado por `key` em `_ema_state`.

  new = alpha * value + (1 - alpha) * prev

  - `alpha` padrão: `EMA_ALPHA = 0.25`.
  - Valores menores de `alpha` → suavização mais forte (mais lenta); maiores → resposta mais rápida.

- O EMA é aplicado a cada componente (ombro, neck_lat, neck_fwd, etc.) para evitar flutuações bruscas de frame a frame.

---

## Cores / Visualização das barras

- Cada score é convertido para cor BGR por `score_to_color(score)`:

  - score ∈ [0,1].
  - Para score >= 0.5 faz rampa amarelo→verde; para score < 0.5 faz rampa vermelho→amarelo.
  - Retorna um tuple (B, G, R) para desenhar as barras e linhas.

- As barras HUD mostram o valor contínuo do score (0..1) e são desenhadas por `draw_bar`.

---

## Parâmetros principais (padrões)

- VISIBILITY_THRESHOLD = 0.5  # visibilidade mínima de um landmark para ser considerado válido
- EMA_ALPHA = 0.25
- FPS_ESTIMATE = 30
- POSTURE_WINDOW_SEC = 30
- BAD_POSTURE_THRESHOLD = 0.45
- Shoulder max angle para score: max_angle = 20.0 (graus)
- Neck lateral max angle: max_angle = 24.0 (graus)
- Neck forward mapping: ratio thresholds: 0.25 (pior) → 0.65 (bom)

Ajustar esses parâmetros afeta sensibilidade e comportamento do sistema.

---

## Casos de borda e recomendações

- Se os landmarks necessários não estiverem visíveis (por ex. ombros fora do quadro), aquela métrica é omitida do `posture`.
- O `global_score` apenas considera componentes presentes; com poucos componentes o `global_score` pode não refletir toda a postura do corpo.
- A normalização por `shoulder_width` reduz variação por distância/câmera, mas em ângulos muito inclinados pode perder precisão.
- Recomenda-se ajustar `POSTURE_WINDOW_SEC` e `EMA_ALPHA` conforme a aplicação (alertas em tempo real exigem alpha maior / janela menor).

---

## Exemplos numéricos

- Ombros: se os ombros estiverem quase horizontais (angle ≈ 2°) → score_raw ≈ 1 - (2/20) = 0.90 → após EMA pode ficar ≈ 0.88.
- Pescoço frontal: se ratio = 0.30 → raw_neck_fwd = clamp((0.30 - 0.25) / 0.40, 0, 1) = 0.125 → score_fwd ≈ 0.125 (suavizado pela EMA).
- Global: com shoulder=0.88, neck=0.6 → global_score = (0.88+0.6)/2 = 0.74 → considerado bom se > 0.45.

---

## Onde no código essas métricas aparecem

- `angle_to_score` — normalização de ângulo → score raw (função central).
- `ema(...)` — suavização temporal por chave.
- Cálculo de ângulos e ratios em `with mp_pose.Pose(...) as pose: ...` dentro de `mediapipe/test_mp.py`.
- HUD: `draw_bar` + `score_to_color` desenham a visualização.

---

## Próximos passos (opcionais)

- Exportar métricas por minuto/por sessão para CSV para análise posterior.
- Adicionar métricas temporais adicionais (tempo médio de cabeça inclinada por minuto, número de eventos "sustained bad posture > 10s").
- Substituir a função `min(score_lat, score_fwd)` por uma combinação ponderada se quiser reduzir influência extrema de uma componente.

---

Se quiser, eu adapto este documento com fórmulas LaTeX, diagramas ou exemplos gerados a partir de frames reais do seu webcam.
