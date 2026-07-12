## Resumo da Abordagem

O projeto utiliza o método de extração 2D, inspirado pelo **Projeto SAPO** (Ferreira et al., 2010), que valida cientificamente a extração de ângulos posturais a partir do alinhamento de pontos anatômicos bidimensionais usando trigonometria no plano frontal.
As métricas são avaliadas utilizando uma calibração base (posição inicial ereta do usuário) e o cálculo de desvios relativos.

---

## 1. Ombros (Assimetria Horizontal)

- **Pontos usados:** Landmarks 11 (Ombro Esquerdo) e 12 (Ombro Direito).
- **Referências Científicas:**
  - O cálculo da assimetria de ombros no plano frontal é embasado na fotogrametria clássica, onde a extração bidimensional do ângulo absoluto entre os acrômios indica o desvio postural da cintura escapular.
- **Limiares heurísticos do software (faixas de referência adotadas pelo projeto, inspiradas na avaliação clínica de assimetria postural):**
  - **<= 2°**: Normal (Tolerância anatômica)
  - **2° a 10°**: Atenção (Assimetria tônica ou fadiga postural)
  - **> 10°**: Perigo (Indicador clínico que exige investigação para desvios estruturais como escoliose).
- **Cálculo:** É extraído o ângulo horizontal absoluto entre os dois ombros. A pontuação é gerada com base no desvio entre o ângulo atual e o ângulo calibrado (`BASE_ANGLE_SHOULDER`), penalizado conforme o limite estabelecido em configuração.

---

## 2. Pescoço (Desvio Lateral)

- **Pontos usados:** Landmark 0 (Nariz) e o ponto médio entre 11 e 12 (Centro do Pescoço/Tronco).
- **Referências Científicas:** Inspirado no método **RULA** e na **ISO 11226**. O RULA penaliza (+1 no score) qualquer flexão lateral do pescoço, e a ISO 11226 recomenda a manutenção da simetria postural com limites para inclinações cervicais estáticas. No software, adota-se um limiar heurístico (~15°) para equilibrar tolerância prática e fadiga de alertas.
- **Cálculo:** Ângulo do vetor formado pelo Nariz e o Centro do Pescoço em relação à vertical. O desvio é calculado em relação à calibração inicial (`BASE_ANGLE_NECK`).

---

## 3. Pescoço Frontal (Forward Head Posture - FHP)

- **Pontos usados:** 0 (Nariz), 2 e 5 (Olhos), 7 e 8 (Orelhas), 11 e 12 (Ombros).
- **Referências Científicas:** 
  - Proxy 2D para medição do Ângulo Craniovertebral (CVA). **Yip et al. (2008)** estabelecem CVA < 50° como indicador de risco de FHP; enquanto **Ruivo et al. (2014)** validam o método fotogramétrico para avaliação cervical e reportam prevalência de FHP em adolescentes.
  - Referência de Carga Biomecânica: **Hansraj (2014)** aponta que a flexão da cabeça aumenta progressivamente a carga na coluna cervical (atingindo ~12 kg a 15° de flexão, podendo chegar a ~27 kg a 60°).
- **Cálculo (Abordagem 2D Pura - Slump e Pitch):**
  Ignora-se a profundidade (eixo Z) e foca-se na compressão vertical e inclinação do rosto:
  1. **Largura de Referência:** Distância Euclidiana entre os ombros (para independência da distância da câmera).
  2. **Slump (Desabamento Vertical):** Distância vertical pura entre a média dos ombros e a média dos olhos, normalizada pela largura dos ombros. Quando o pescoço é curvado para frente/baixo, essa distância encolhe.
  3. **Pitch (Inclinação do Queixo):** Distância vertical entre a média das orelhas e o nariz, também normalizada. Quando a cabeça vai para frente, o queixo sobe para olhar a tela, alterando essa distância no eixo Y.
  
  Essas métricas são suavizadas e comparadas com a calibração inicial (`BASE_SLUMP` e `BASE_PITCH`). Se o desvio ultrapassar a tolerância configurada, uma penalidade severa é aplicada na pontuação.

---

## 4. Cabeça (Inclinação Lateral / Head Roll)

- **Pontos usados:** Olhos (2, 5), Orelhas (7, 8) e Boca (9, 10).
- **Referências Científicas:** **ISO 11226** (Princípio de Simetria) e **Kapandji** (Fisiologia Articular). Limiares curtos (5° a 15°) são usados para garantir permanência na "zona neutra" segura, prevenindo o desgaste dos discos cervicais.
- **Cálculo:** Média dos ângulos horizontais oculares, auriculares e bucais, ajudando a reduzir o ruído (*jitter*). O valor é comparado com o rolamento base calibrado (`BASE_HEAD_ROLL`).

---

## Suavização e Feedback Visual

Para evitar alertas falsos ou oscilações devido ao ruído da câmera e movimentos curtos:
- **EMA (Exponential Moving Average):** Todas as pontuações brutas passam por uma suavização temporal, filtro passa-baixa com fundamento em **Winter (2009)**, que estabelece a filtragem de ruído cinemático como mandatória na biomecânica computacional.
- **Alertas e Setas:** Quando um desvio considerável é detectado, o HUD utiliza setas vetoriais para guiar visualmente o usuário a corrigir a postura exata (ex: baixar o queixo, esticar as costas, nivelar os ombros).

---

## Referências Bibliográficas

**FERREIRA, E. A. G. et al.** Postural Assessment Software (PAS/SAPO): Validation and reliability. *Clinics*, São Paulo, v. 65, n. 7, p. 675-681, 2010.

**HANSRAJ, K. K.** Assessment of stresses in the cervical spine caused by posture and position of the head. *Surgical Technology International*, San Francisco, v. 25, p. 277-279, nov. 2014.

**INTERNATIONAL ORGANIZATION FOR STANDARDIZATION (ISO).** *ISO 11226:2000*: Ergonomics — Evaluation of static working postures. Genebra: ISO, 2000. (No Brasil: ABNT NBR ISO 11226).

**KAPANDJI, A. I.** *Fisiologia articular*: tronco e coluna vertebral. 6. ed. Rio de Janeiro: Guanabara Koogan, 2000. v. 3.

**McATAMNEY, L.; CORLETT, E. N.** RULA: a survey method for the investigation of work-related upper limb disorders. *Applied Ergonomics*, v. 24, n. 2, p. 91-99, 1993.

**RUIVO, R. M.; PEZARAT-CORREIA, P.; CARITA, A. I.** Cervical and shoulder postural assessment of adolescents between 15 and 17 years old and association with upper quadrant pain. *Brazilian Journal of Physical Therapy*, São Carlos, v. 18, n. 4, p. 364-371, ago. 2014.

**NEGRINI, S. et al.** 2016 SOSORT guidelines: orthopaedic and rehabilitation treatment of idiopathic scoliosis during growth. *Scoliosis and Spinal Disorders*, v. 13, art. 3, 2018.

**WINTER, D. A.** *Biomechanics and Motor Control of Human Movement*. 4. ed. Hoboken: John Wiley & Sons, 2009.

**YIP, C. H. T.; CHIU, T. T. W.; POON, A. T. K.** The relationship between head posture and severity and disability of patients with neck pain. *Manual Therapy*, Edinburgh, v. 13, n. 2, p. 148-154, maio 2008.
