# Big Leap: assistente de Google Ads

Gera um relatório semanal das campanhas e alerta sobre problemas:

| Área | O que verifica |
|---|---|
| **Tracking** | Auto-tagging desligado; dias seguidos sem conversão com cliques acontecendo; ação de conversão primária sem disparar há 14 dias; campanha que convertia e zerou |
| **Performance** | Queda de conversões e alta de CPA semana contra semana, por campanha |
| **Orçamento** | Campanhas de Search perdendo impressão por orçamento |
| **Palavras-chave** | Gasto alto sem conversão; CPA muito acima do alvo; Quality Score baixo |
| **Termos de busca** | Termos gastando sem converter (candidatos a negativa) |
| **Anúncios** | Anúncios reprovados ou com aprovação limitada |

Os limites ficam em [`config.yaml`](config.yaml).

## Uso

```bash
pip install -r requirements.txt
python -m gads check    # testa a conexão
python -m gads report   # gera reports/AAAA-MM-DD.md
python -m gads alerts   # só os alertas
python -m pytest        # testes da lógica de alertas
```

## Configuração das credenciais (uma vez só)

A API do Google Ads precisa de 5 coisas: **developer token**, **client ID**, **client secret**, **refresh token** e o **ID da conta** (mais o ID da MCC, se o acesso for por uma).

### 1. Google Cloud (OAuth)
1. Em [console.cloud.google.com](https://console.cloud.google.com), crie ou escolha o projeto.
2. **APIs e serviços › Biblioteca**: ative a **Google Ads API**.
3. **Tela de consentimento OAuth** (Google Auth Platform): tipo *Externo*, adicione seu e-mail como usuário de teste.
   Depois, em **Público-alvo**, clique em **Publicar app** (status *Em produção*). Enquanto o app fica em *Teste*, o refresh token **expira a cada 7 dias**.
4. **Credenciais › Criar credenciais › ID do cliente OAuth**, tipo **App para computador** (Desktop). Baixe o JSON.

### 2. Developer token
1. O token só existe numa **conta de administrador (MCC)** do Google Ads. Se ainda não tiver, crie em [ads.google.com/home/tools/manager-accounts](https://ads.google.com/home/tools/manager-accounts/) e vincule a conta da Big Leap a ela.
2. Na MCC: **Administrador › Central de API**. Preencha o formulário e copie o developer token.
3. O token novo vem com acesso limitado (contas de teste). Para ler a conta real, peça o **Basic Access** na própria Central de API. A aprovação costuma levar alguns dias úteis.

### 3. Refresh token (rodar no seu computador)
```bash
pip install google-auth-oauthlib
python scripts/generate_refresh_token.py client_secret_XXXX.json
```
Faça login com a conta Google que tem acesso ao Google Ads. O script imprime o client ID e o refresh token.

### 4. Variáveis de ambiente
Preencha as variáveis de [`.env.example`](.env.example). Localmente, copie para `.env`. No ambiente cloud do Claude Code, cadastre como variáveis/segredos do ambiente. **Nunca** faça commit desses valores nem cole no chat.
