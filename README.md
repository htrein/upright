# Upright

## Pré-requisitos de sistema

- Conda (Miniconda/Anaconda) instalado e inicializado (`conda init bash`).
- Para acesso à câmera: permissões de dispositivo (usuário no grupo `video` em Linux) e suporte V4L2.

## Passo a passo para rodar o MediaPipe

1. **Criar o ambiente Conda**

Execute no diretório raiz do repositório para criar o ambiente com as dependências necessárias:

```bash
conda env create -f environment-mediapipe.yml
```

2. **Tornar o script executável e rodar o demo**

Execute os comandos abaixo a partir do diretório raiz do projeto para dar permissão de execução ao script e iniciá-lo:

```bash
chmod +x scripts/run_mediapipe.sh

# Rodar o demo mediapipe
./scripts/run_mediapipe.sh
```

## Permissões de câmera em Linux (Troubleshooting)

Caso encontre problemas para abrir a câmera, certifique-se de que seu usuário é membro do grupo `video` para acessar `/dev/video*`.
Para adicionar o usuário ao grupo `video` (é necessário fazer logout/login depois):

```bash
sudo usermod -aG video $USER
```