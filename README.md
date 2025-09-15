# Sistema de Automação de Login e Dashboard
Automatiza o login de alunos em uma plataforma educacional e fornece um dashboard em tempo real para monitorar acessos e detectar possíveis violações de regras.

[creenshot da interface]  
[screenshot do dashboard]

Funcionalidades principais
- Automação de Login: Interface gráfica (Tkinter) para os alunos selecionarem seu perfil e acessarem a plataforma via Selenium.
- Registro de Atividade: Todos os logins são registrados em uma planilha do Google Sheets para auditoria.
- Dashboard de Análise: Painel (Streamlit + Pandas) para administradores visualizarem e filtrarem dados de uso.
- Detecção de Alertas: O dashboard identifica e alerta sobre violações (ex.: mais de 2 contas diferentes na mesma máquina em 1 hora).

Ferramentas
- Python 3.8+
- Selenium (automação web)
- Tkinter (interface gráfica)
- Streamlit & Pandas (dashboard)
- gspread & Google Cloud (integração com Google Sheets)

---
Índice
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Execução](#execução)
- [Gerando um executável .exe (Opcional)](#gerando-um-executável-exe-opcional)
- [Como funciona (visão geral)](#como-funciona-visão-geral)
- [Detecção de alertas](#detecção-de-alertas)
- [Problemas comuns](#problemas-comuns)

## Pré-requisitos
- Python 3.8 ou superior
- Google Chrome (compatível com a versão do ChromeDriver)
- credentials.json: arquivo de credenciais da conta de serviço do Google Cloud com acesso ao Google Sheets
- (Opcional) PyInstaller para gerar um executável

## Instalação
1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/seu-repositorio.git
cd seu-repositorio
```

2. Crie e ative um ambiente virtual (recomendado)
- Windows (PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
- Windows (CMD)
```cmd
python -m venv venv
.\venv\Scripts\activate
```
- macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Instale as dependências
```bash
pip install -r requirements.txt
```

## Configuração
1. Renomeie o arquivo `.env.example` para `.env`.
2. Abra `.env` e configure o caminho para o `credentials.json` e outras variáveis necessárias. Exemplo:
```env
# Caminho absoluto para o arquivo de credenciais da conta de serviço
GOOGLE_CREDENTIALS_PATH="/caminho/para/credentials.json"
# Exemplo no Windows (escape de barras ou use barras normais)
# GOOGLE_CREDENTIALS_PATH="C:\\Users\\Alan\\Documentos\\chaves\\credentials.json"
# ID ou URL da planilha do Google Sheets onde os logs serão gravados
GOOGLE_SHEET_ID="seu_google_sheet_id_aqui"
```

3. Compartilhe a planilha com o e-mail da conta de serviço (do `credentials.json`) com permissão de edição.

Observação: certifique-se de que a versão do ChromeDriver corresponda à versão do Google Chrome instalada. Você pode usar webdriver-manager ou configurar manualmente o executável.

## Execução

➤ Aplicação do Aluno (Interface de Login — Tkinter + Selenium)
```bash
python interface_login.py
```
- Abra a interface, selecione o perfil do aluno e clique em "Entrar".
- O Selenium abrirá o navegador e fará o processo de login automatizado.
- Cada tentativa de login será registrada na planilha do Google.

➤ Dashboard do Administrador (Streamlit)
```bash
streamlit run dashboard_adm.py
```
- O dashboard carrega os dados da planilha e apresenta:
  - Tabela de acessos
  - Gráficos de uso
  - Alertas e indicadores de violações

## Gerando um executável .exe (Opcional)
Para distribuir a aplicação do aluno sem exigir instalação do Python:

1. Instale PyInstaller:
```bash
pip install pyinstaller
```

2. Coloque uma cópia do `credentials.json` na mesma pasta do `interface_login.py` (ou ajuste a lógica para apontar ao caminho correto).

3. Gere o executável:
- Windows (observe o separador `;` no --add-data)
```bash
pyinstaller --onefile --windowed --add-data "credentials.json;." interface_login.py
```
- macOS / Linux (se necessário, use `:` como separador)
```bash
pyinstaller --onefile --windowed --add-data "credentials.json:." interface_login.py
```

O executável final ficará na pasta `dist/`.

Atenção: dependendo da forma como o Selenium e drivers são gerenciados, pode ser necessário empacotar o ChromeDriver ou garantir que o executável encontre o driver em runtime.

## Como funciona (visão geral)
- O aluno abre a interface Tkinter e escolhe o perfil.
- O script usa Selenium para abrir o navegador, preencher credenciais e efetuar login.
- Ao final (ou em falha), o evento é gravado numa planilha do Google com informações como: timestamp, usuário, máquina (hash ou identificador), IP (se coletado), e resultado.
- O dashboard Streamlit lê a planilha, agrega dados e exibe painéis e regras de alerta.

## Detecção de alertas
Exemplo de regras implementadas (configuráveis):
- Mais de 2 contas logadas a partir da mesma máquina em 1 hora → gera alerta.

O dashboard mostra uma lista de alertas e indicadores com filtros por período e por máquina/usuário.

## Problemas comuns
- Erro de autenticação do Google Sheets:
  - Verifique se o `credentials.json` está correto e se a planilha foi compartilhada com a conta de serviço.
- Chrome/ChromeDriver incompatível:
  - Atualize o ChromeDriver para a versão correspondente ao Chrome instalado.
- Permissões do sistema ao rodar .exe:
  - Em ambientes corporativos, antivírus ou políticas podem bloquear o executável. Adicione exceção ou assine o binário se necessário.

## Contribuição
Contribuições são bem-vindas! Abra uma issue descrevendo o que deseja melhorar ou envie um pull request com correções/novas funcionalidades.
