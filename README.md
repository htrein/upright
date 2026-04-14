Arquivos úteis adicionados
- `environment-trt_pose.yml` — dependências base para o demo `trt_pose`.
- `environment-mediapipe.yml` — dependências base para o demo `mediapipe`.
- `scripts/run_trt_pose.sh` — script para ativar o ambiente e rodar `camera_demo.py`.
- `scripts/run_mediapipe.sh` — script para ativar o ambiente e rodar `test_mp.py`.

Resumo do que é necessário (pré-requisitos de sistema)
- NVIDIA driver instalado e funcional (compatível com sua GPU).
- CUDA Toolkit instalado (o local padrão esperado pelos scripts é `/usr/local/cuda`).
- cuDNN instalado se necessário para performance (opcional, recomendado).
- Conda (Miniconda/Anaconda) instalado e inicializado (`conda init bash`).
- Git e ferramentas de compilação básicas (em distribuições Debian/Ubuntu: `build-essential`, `pkg-config`, `ffmpeg` onde necessário).
- Para acesso à câmera: permissões de dispositivo (usuário no grupo `video` em Linux) e suporte V4L2.

Verificações rápidas (execute estes comandos para checar o ambiente do sistema)

```bash
# mostra versão do driver/daemon e GPUs detectadas
nvidia-smi

# se tiver nvcc (CUDA Toolkit) instalado, mostra a versão
nvcc --version || echo "nvcc not found (CUDA toolkit may not be installed)"

# verifica que conda está instalada e mostra base path
conda --version
conda info --base

# verifica python + torch (depois de instalar PyTorch) — rode dentro do env
python3 -c "import torch; print('torch:', torch.__version__); print('cuda available:', torch.cuda.is_available()); print('cuda ver (torch):', torch.version.cuda)"
```

1) Criar os ambientes Conda (ambientes base)

Execute (no diretório raiz do repositório):

```bash
conda env create -f environment-trt_pose.yml
conda env create -f environment-mediapipe.yml
```

Os YAMLs contêm pacotes base. NÃO fixamos o binário do PyTorch por padrão,
porque o build correto depende da versão do CUDA presente no host (veja abaixo).

2) Instalar PyTorch compatível com sua versão de CUDA (passo crítico para trt_pose)

Escolha a versão do PyTorch que corresponda à sua versão de CUDA. Exemplos de
comandos `conda` (recomendado quando o pacote `pytorch-cuda` estiver disponível
no canal `nvidia`):

```bash
# Para CUDA 12.1
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia

# Para CUDA 11.8
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia

# Para CUDA 11.7
conda install pytorch torchvision torchaudio pytorch-cuda=11.7 -c pytorch -c nvidia
```

Se você prefere `pip`, use as URLs / instruções oficiais do PyTorch (substitua a
whl pela que corresponde à sua CUDA):

```bash
# Exemplo (CUDA 11.8) - ajuste conforme necessário
pip3 install torch torchvision --extra-index-url https://download.pytorch.org/whl/cu118
```

Após instalar, ative o ambiente e verifique com o snippet Python em "Verificações rápidas".

3) Tornar os scripts executáveis e rodar os demos

```bash
chmod +x scripts/run_trt_pose.sh scripts/run_mediapipe.sh

# trt_pose (padrão: axis_monitor)
./scripts/run_trt_pose.sh [nome_do_env_conda]

# mediapipe (padrão: mp_fix)
./scripts/run_mediapipe.sh [nome_do_env_conda]
```

Os scripts fazem `conda activate` (usam o `conda` inicializado) e exportam as
variáveis `CUDA_HOME`, `PATH` e `LD_LIBRARY_PATH` apontando para
`/usr/local/cuda`. Se o seu CUDA está em outro diretório, edite os scripts ou
exporte as variáveis antes de executar.

Baixar o arquivo de pesos usado pelo demo (`resnet18_baseline_att_224x224_A_epoch_249.pth`)
---------------------------------------------------------------------------------

O demo `trt_pose/tasks/human_pose/camera_demo.py` espera encontrar o arquivo de
pesos `resnet18_baseline_att_224x224_A_epoch_249.pth` no diretório
`trt_pose/tasks/human_pose/` (nome relativo). Se este arquivo não estiver
presente no repositório, siga um destes métodos para obtê-lo:

1) Usar o script fornecido (recomendado):

```bash
chmod +x scripts/download_weights.sh
./scripts/download_weights.sh
```

O script baixa o arquivo do repositório público e o salva em
`trt_pose/tasks/human_pose/resnet18_baseline_att_224x224_A_epoch_249.pth`.

2) Baixar manualmente com wget/curl:

```bash
mkdir -p trt_pose/tasks/human_pose
wget -O trt_pose/tasks/human_pose/resnet18_baseline_att_224x224_A_epoch_249.pth \
  "https://raw.githubusercontent.com/make2explore/Real-Time-Hand-Pose-Estimation-on-Jetson-Nano/main/Pre-Trained%20Models/trt_pose/resnet18_baseline_att_224x224_A_epoch_249.pth"
```

ou com curl:

```bash
curl -L -o trt_pose/tasks/human_pose/resnet18_baseline_att_224x224_A_epoch_249.pth \
  "https://raw.githubusercontent.com/make2explore/Real-Time-Hand-Pose-Estimation-on-Jetson-Nano/main/Pre-Trained%20Models/trt_pose/resnet18_baseline_att_224x224_A_epoch_249.pth"
```

3) Verificação (opcional):

Após o download, confirme que o arquivo existe e verifique o tamanho / checksum:

```bash
ls -lh trt_pose/tasks/human_pose/resnet18_baseline_att_224x224_A_epoch_249.pth
sha256sum trt_pose/tasks/human_pose/resnet18_baseline_att_224x224_A_epoch_249.pth
```

Se preferir, posso adicionar um checksum oficial no README e bloquear o arquivo
no repositório com LFS; diga se quer que eu faça isso.

Permissões de câmera e vídeo em Linux
- Certifique-se de que seu usuário é membro do grupo `video` ou execute o demo
  com permissões suficientes para acessar `/dev/video*`.
- Para adicionar o usuário ao grupo `video` (logout/login necessário):

```bash
sudo usermod -aG video $USER
```

Checklist rápido (passo-a-passo)
1. Instalar NVIDIA driver e (opcional) CUDA toolkit.
2. Instalar Conda (Miniconda) e rodar `conda init bash`.
3. Criar os ambientes:
   - `conda env create -f environment-trt_pose.yml`
   - `conda env create -f environment-mediapipe.yml`
4. Ativar o ambiente e instalar o PyTorch compatível com sua CUDA (veja comandos acima).
5. Dar permissão de execução aos scripts: `chmod +x scripts/*.sh`.
6. Rodar: `./scripts/run_trt_pose.sh axis_monitor` ou `./scripts/run_mediapipe.sh mp_fix`.

Troubleshooting rápido
- `conda activate` não funciona em scripts: execute `conda init bash` no shell
  interativo e abra um novo terminal. Os scripts usam `source $(conda info --base)/etc/profile.d/conda.sh`.
- Torch não detecta CUDA: reinstale PyTorch com o pacote que corresponda à
  sua versão do CUDA; verifique `nvidia-smi`/`nvcc --version`.
- Erros de OpenCV ou câmera: verifique permissões (`/dev/video*`) e dependências do sistema.
- `pip install mediapipe` falha: tente Docker ou consulte docs do MediaPipe.