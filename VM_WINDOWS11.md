# Rodar o `vote.py` em uma VM Windows 11 (sem Docker)

Este projeto depende de um Chrome instalado no Windows e usa CDP (`--remote-debugging-port=9222`).
Por isso, a forma mais simples (e fiel ao que voce ja roda) e manter em uma VM Windows 11.

## 1) Pre-requisitos na VM

- Windows 11 com acesso via RDP (opcional)
- Python 3.x (marque "Add python to PATH" no instalador)
- Google Chrome instalado
- Git (opcional, se for clonar ao inves de copiar os arquivos)

## 2) Copiar o projeto para a VM

Opcoes:
- `git clone ...`
- Copiar a pasta do projeto (zip/SMB/SCP)

## 3) Configurar variaveis (.env)

Crie/ajuste um `.env` na raiz (voce pode partir de `.env.example`).

Campos essenciais:
- `SITE_URL`
- `LOGIN_URL` (se aplicavel)
- `CANDIDATO`
- `USER_EMAIL` (pode ser separado por virgula)
- `USER_PASSWORD`

Opcional (ajustes de execucao):
- `MAIN_USER_DATA_DIR` (ex.: `C:\\chrome-debug`)
- `PROFILE_DIR` (ex.: `Default` / `Profile 1` / `Trabalho`)
- `DEBUG_PORT` (padrao: `9222`)
- `BRING_TO_FRONT` (`1`/`0`)
- `MAX_INTERATIONS_NOW` (padrao: `20`)

## 4) Instalar dependencias e rodar

No PowerShell, na raiz do repo:

```powershell
scripts\windows\bootstrap.ps1
$env:INSTANCE_ID=1; scripts\windows\run_vote.ps1
```

Se for a primeira vez numa VM "zerada", o `MAIN_USER_DATA_DIR` pode nao ter profiles ainda; o script vai deixar o Chrome criar o `PROFILE_DIR` automaticamente.

## 6) Rodar 3 instancias (1, 2 e 3)

Abra 3 terminais (PowerShell) separados e rode um em cada:

```powershell
$env:INSTANCE_ID=1; scripts\windows\run_vote.ps1
```

```powershell
$env:INSTANCE_ID=2; scripts\windows\run_vote.ps1
```

```powershell
$env:INSTANCE_ID=3; scripts\windows\run_vote.ps1
```

Isso separa automaticamente:
- Porta do DevTools: `DEBUG_PORT_BASE + (INSTANCE_ID-1)` (padrao `9222`, `9223`, `9224`)
- Pasta do Chrome: `C:\\chrome-debug-<id>` (se voce nao definir `MAIN_USER_DATA_DIR` no `.env`)
- Pasta de artifacts: `artifacts\\instance_<id>` (se voce nao definir `ARTIFACTS_DIR` no `.env`)

Opcao: iniciar tudo com 1 comando (abre 3 janelas):

```powershell
scripts\windows\run_all.ps1 -NewWindows
```

## 5) Rodar "sempre ligado" (opcional)

Se voce quiser deixar rodando sem ficar com o terminal aberto, use o Agendador de Tarefas do Windows para executar:

- Programa/script: `powershell.exe`
- Argumentos: `-ExecutionPolicy Bypass -File E:\\caminho\\do\\repo\\scripts\\windows\\run_vote.ps1`
- Iniciar em: `E:\\caminho\\do\\repo`

Obs.: se `BRING_TO_FRONT=1`, a automacao pode abrir/jogar janela para frente. Em VM via RDP isso pode ser desejavel.
