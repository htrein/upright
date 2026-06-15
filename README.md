# 🧍 Upright — Posture Tracking em Tempo Real

**Upright** é um sistema de monitoramento de postura corporal em tempo real que usa a câmera do computador para detectar má postura (ombros caídos, pescoço inclinado/projetado para frente) e gerar alertas visuais instantâneos, além de registrar um histórico de sessões no banco de dados local.

> Versão atual: **1.0** · Python 3.10 · MediaPipe Tasks API · SQLite3

---

## Índice

1. [Compatibilidade por sistema operacional](#compatibilidade)
2. [Pré-requisitos](#pré-requisitos)
3. [Instalação](#instalação)
4. [Baixando os modelos de IA](#baixando-os-modelos-de-ia)
5. [Como rodar](#como-rodar)
6. [Argumentos disponíveis](#argumentos-disponíveis)
7. [Atalhos de teclado](#atalhos-de-teclado)
8. [Gerando um executável](#gerando-um-executável)
9. [Estrutura do projeto](#estrutura-do-projeto)
10. [Dependências](#dependências)
11. [Banco de dados](#banco-de-dados)
12. [Troubleshooting](#troubleshooting)

---

## Compatibilidade

| Funcionalidade | Linux ✅ | Windows ⚠️ | macOS ⚠️ |
|---|---|---|---|
| Rastreamento de postura (CPU) | ✅ | ✅ | ✅ |
| Rastreamento de postura (GPU) | ✅ | ❌ | ❌ |
| Modo fullscreen | ✅ | ✅ | ⚠️ Pode ter bugs |
| Scripts `.sh` nativos | ✅ | ❌ (usar Git Bash/WSL) | ✅ |
| Histórico e relatórios | ✅ | ✅ | ✅ |

### Linux (recomendado)
Suporte completo, incluindo aceleração por GPU via OpenGL ES (NVIDIA/AMD). Testado em Ubuntu 22.04+.

### Windows
O delegate GPU do MediaPipe Tasks usa OpenGL ES, que **não é suportado nativamente no Windows**. O app roda normalmente em **modo CPU** (`--cpu`, que é o padrão). Os scripts `.sh` precisam do Git Bash ou WSL para executar.

### macOS
O delegate GPU usa Metal no macOS mas **não é oficialmente suportado** pela versão atual do MediaPipe Tasks. Rode sempre com `--cpu`. Os scripts `.sh` rodam nativamente no Terminal.

---

## Pré-requisitos

### Todos os sistemas
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) ou [Anaconda](https://www.anaconda.com/) instalado e inicializado (`conda init bash` ou `conda init zsh`).
- Webcam conectada e funcionando.
- `curl` ou `wget` para baixar os modelos de IA.

### Linux (adicional)
- Usuário no grupo `video` para acesso à câmera (ver [Troubleshooting](#troubleshooting)).
- Para modo GPU: driver NVIDIA/AMD com suporte a OpenGL ES 3.1+.

---

## Instalação

### 1. Clone o repositório

```bash
git clone <url-do-repositório>
cd upright
```

### 2. Crie o ambiente Conda

```bash
conda env create -f environment-mediapipe.yml
```

Esse comando cria o ambiente chamado `mediapipe` com todas as dependências Python necessárias (Python 3.10, OpenCV, MediaPipe, etc).

> Se preferir usar um nome diferente para o ambiente, edite a linha `name:` no arquivo `environment-mediapipe.yml`.

### 3. Baixe os modelos de IA

Os modelos de detecção não estão incluídos no repositório por serem arquivos grandes. Baixe-os com:

```bash
chmod +x scripts/download_mp_tasks.sh
./scripts/download_mp_tasks.sh
```

Isso irá baixar automaticamente para `mediapipe/models/`:
- `pose_landmarker_full.task` — Detecção de landmarks corporais (ombros, pescoço)
- `selfie_segmenter.tflite` — Segmentação de pessoa para modo privacidade

---

## Como rodar

### Usando o script (recomendado)

```bash
chmod +x scripts/run_mediapipe.sh

# Rodar com CPU (padrão — compatível com todos os sistemas)
./scripts/run_mediapipe.sh

# Rodar com GPU (Linux com OpenGL ES — mais rápido)
./scripts/run_mediapipe.sh mediapipe --gpu

# Especificar nome do ambiente conda + modo de processamento
./scripts/run_mediapipe.sh <nome_do_ambiente> [--cpu|--gpu]
```

### Rodando diretamente com Python

```bash
conda activate mediapipe
cd mediapipe/

# CPU (padrão)
python3 main.py

# GPU (Linux)
python3 main.py --gpu
```

---

## Argumentos disponíveis

| Argumento | Descrição | Compatibilidade |
|---|---|---|
| _(nenhum)_ | Roda em modo CPU (comportamento padrão) | Todos |
| `--cpu` | Força modo CPU explicitamente | Todos |
| `--gpu` | Usa GPU para inferência (OpenGL ES delegate) | Apenas Linux |

**Exemplo:**
```bash
python3 main.py --gpu     # GPU no Linux
python3 main.py --cpu     # CPU em qualquer sistema
```

> O sistema faz **fallback automático para CPU** se `--gpu` for passado mas a GPU não estiver disponível ou incompatível. Uma mensagem de aviso é exibida no terminal.

---

## Atalhos de teclado

Esses atalhos funcionam com a janela do app em foco:

| Tecla | Ação |
|---|---|
| `C` | Calibrar postura atual como base (use quando estiver sentado reto!) |
| `S` | Abrir janela de configurações (sensibilidade) |
| `R` | Gerar relatório HTML da sessão atual e abrir no navegador |
| `P` | Ativar/desativar modo privacidade (oculta o vídeo) |
| `M` | Alternar estilo de privacidade: silhueta → blur → mosaico |
| `Space` | Pausar/retomar o rastreamento |
| `F` | Alternar entre tela cheia e janela normal |
| `Esc` | Encerrar o programa |

---

## Fluxo de uso típico

1. **Inicie o app** → faça login ou cadastre-se na janela de autenticação.
2. **Sente-se em posição ereta** → pressione `C` para calibrar sua postura base.
3. **Trabalhe normalmente** → o app monitora em tempo real no canto da tela.
4. **Ajuste a sensibilidade** → pressione `S` se os alertas estiverem muito frequentes ou raros.
5. **Ao terminar** → pressione `R` para ver o relatório do dia, ou `Esc` para sair.

---

## Gerando um executável

Você pode gerar um **único arquivo executável** que não exige Python instalado para rodar.

### Pré-requisito
Ter o ambiente conda com as dependências criado (etapa de instalação).

### Gerar o executável

```bash
chmod +x scripts/build_exe.sh
./scripts/build_exe.sh [nome_do_ambiente]

# Exemplo:
./scripts/build_exe.sh mediapipe
```

O executável será gerado em: `dist/upright`

### Usando o executável

```bash
# CPU (padrão, compatível com tudo)
./dist/upright

# GPU (apenas Linux)
./dist/upright --gpu
```

### ⚠️ Avisos importantes sobre executáveis

- O executável gerado é **específico para o sistema operacional** onde foi buildado. Um executável Linux **não roda** no Windows e vice-versa.
- O arquivo `posture_history.db` (banco de dados) e a pasta `models/` são lidos/criados **no mesmo diretório de onde o executável for executado**.
- Para distribuir para outros sistemas, o build precisa ser feito naquele sistema.

| SO Alvo | Como gerar |
|---|---|
| Linux | Rodar `build_exe.sh` no Linux |
| Windows | Instalar Python + PyInstaller no Windows e rodar `pyinstaller` manualmente |
| macOS | Rodar `build_exe.sh` no macOS |

---

## Estrutura do projeto

```
upright/
├── environment-mediapipe.yml   # Dependências do ambiente Conda
├── README.md
│
├── mediapipe/                  # Código-fonte principal
│   ├── main.py                 # Ponto de entrada — loop principal da câmera
│   ├── config.py               # Variáveis de configuração e estado global
│   ├── posture.py              # Lógica de cálculo de ângulos e scores de postura
│   ├── hud.py                  # HUD (cabeçalho visual) sobreposto ao vídeo
│   ├── db.py                   # Banco de dados SQLite (usuários, sessões, logs)
│   ├── auth_window.py          # Janela de autenticação (CustomTkinter)
│   ├── config_window.py        # Janela de configurações (CustomTkinter)
│   ├── privacy.py              # Filtros de privacidade (blur, silhueta, mosaico)
│   ├── generate_report.py      # Gerador de relatório HTML interativo
│   ├── posture_history.db      # Banco de dados local (gerado automaticamente)
│   ├── emissions.csv           # Log de estimativas de emissão de CO₂ (gerado automaticamente)
│   ├── METRICS.md              # Documentação técnica das métricas de postura
│   └── models/                 # Modelos de IA do MediaPipe (baixar via script)
│       ├── pose_landmarker_full.task
│       └── selfie_segmenter.tflite
│
└── scripts/
    ├── run_mediapipe.sh        # Script para rodar o app com conda (suporta --cpu / --gpu)
    ├── build_exe.sh            # Script para gerar executável com PyInstaller
    └── download_mp_tasks.sh    # Script para baixar os modelos de IA
```


---

## Dependências

Gerenciadas automaticamente pelo `environment-mediapipe.yml`:

| Pacote | Versão | Papel |
|---|---|---|
| `python` | 3.10 | Linguagem base |
| `mediapipe` | latest | Detecção de poses e segmentação (Tasks API) |
| `opencv` | latest | Captura de câmera e processamento de imagem |
| `numpy` | latest | Operações matriciais para análise de frames |
| `customtkinter` | latest | Janelas de autenticação e configuração |
| `Pillow` | latest | Suporte a imagens nas janelas Tkinter |
| `matplotlib` | latest | Gráficos para o relatório de postura |
| `absl-py` | latest | Utilitários internos do MediaPipe |
| `protobuf` | latest | Serialização de dados (dependência do MediaPipe) |
| `codecarbon` _(opcional)_ | latest | Estimativa de emissões de CO₂ durante a sessão |

Para instalar `codecarbon` (opcional):
```bash
conda activate mediapipe
pip install codecarbon
```

---

## Banco de dados

O app usa **SQLite3** local, sem servidor. O arquivo `posture_history.db` é criado automaticamente na primeira execução dentro da pasta `mediapipe/`.

### Tabelas

| Tabela | Descrição |
|---|---|
| `users` | Usuários cadastrados (username único, senha com hash SHA-256) |
| `calibrations` | Ângulos de referência calibrados por usuário (ombro, pescoço, cabeça) |
| `user_preferences` | Configurações de sensibilidade (rigidez: Normal / Rigoroso / Relaxado) |
| `sessions` | Registro de cada sessão de uso (início e fim) |
| `posture_logs` | Score de postura registrado a cada ~1s por sessão |

> O banco é criado localmente e **nenhum dado é enviado para a internet**.