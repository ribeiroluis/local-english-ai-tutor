# Prompt para Agente de Código — App de Conversação em Inglês (100% Local, CPU, Open-Source)

Copie e cole o conteúdo abaixo no seu agente de código (Claude Code, Cursor, etc).

---

## PROMPT

Quero que você construa um **aplicativo web de prática de conversação em inglês**, em **Python**, usando **apenas modelos open-source rodando 100% localmente em CPU** (não tenho GPU disponível). O objetivo é um app no estilo dos líderes de mercado (ELSA Speak, Speak, ISSEN, Pingo), mas totalmente self-hosted e gratuito.

### Visão geral do produto
- Foco principal: **conversação livre em inglês com correção de erros em tempo real** (gramática, vocabulário e, se possível, pronúncia).
- Interação por **voz completa**: o usuário fala (STT), a IA responde em texto E em voz (TTS).
- Interface: **aplicação web** (backend em FastAPI, frontend simples em HTML/JS, sem frameworks pesados).
- Tudo deve rodar localmente, sem chamadas a APIs pagas (OpenAI, Google, etc) e sem depender de GPU — todos os modelos devem ter variantes leves o suficiente para rodar em CPU com latência aceitável.

### Funcionalidades essenciais (MVP)
1. **Conversa por voz**: usuário clica em um botão, fala, o áudio é transcrito (STT), enviado ao modelo de linguagem, que responde como um "parceiro de conversação" em inglês, e a resposta é convertida em voz (TTS) e tocada de volta.
2. **Correção de erros**: a cada turno do usuário, o sistema deve identificar erros de gramática/vocabulário/uso e mostrar (em texto, na tela) uma versão corrigida da frase, com uma breve explicação em português do que foi corrigido e por quê.
3. **Histórico de conversa**: manter o contexto da conversa atual (memória de curto prazo) para que a IA responda de forma coerente ao longo do diálogo.
4. **Tópicos/cenários de conversa**: permitir escolher um tema (ex: "small talk", "entrevista de emprego", "pedir comida", "viagem") que ajusta o prompt do sistema/persona da IA.
5. **Nível do aluno**: permitir configurar o nível (iniciante, intermediário, avançado) para calibrar a complexidade da resposta da IA.
6. **Painel de progresso simples**: registrar localmente (SQLite) o número de sessões, principais erros recorrentes e tempo de prática.

### Stack técnica sugerida (ajuste se encontrar algo melhor para CPU)
- **Backend**: Python 3.11+, FastAPI + Uvicorn.
- **Frontend**: HTML + JS puro (ou Jinja2 templates), usando a Web Audio API / MediaRecorder para capturar áudio do microfone no navegador.
- **STT (Speech-to-Text)**: `faster-whisper` (CTranslate2) com modelo `tiny.en` ou `base.en` — otimizado para CPU, muito mais rápido que o whisper.cpp/openai-whisper puro.
- **LLM (geração de conversa e correção)**: rodar via **Ollama** (mais simples de gerenciar localmente) ou `llama-cpp-python` com um modelo quantizado em GGUF. Sugestões de modelo leve para CPU: `Phi-3-mini` (quantizado Q4), `Llama-3.2-3B-Instruct` (Q4_K_M), ou `Qwen2.5-3B-Instruct`. Priorize modelos de 3B parâmetros ou menos para latência razoável em CPU.
- **TTS (Text-to-Speech)**: `Piper TTS` (projeto da Rhasspy) — é leve, roda muito bem em CPU, tem vozes em inglês de boa qualidade (ex: `en_US-lessac-medium` ou `en_US-amy-medium`) e não depende de GPU.
- **Banco de dados**: SQLite (via `sqlite3` ou `SQLModel`) para histórico e progresso.
- **Gerenciamento de dependências**: `pyproject.toml` ou `requirements.txt` claro, com instruções de instalação passo a passo (incluindo como baixar os modelos GGUF/Piper).

### Arquitetura sugerida
```
app/
├── main.py                 # FastAPI app, rotas
├── services/
│   ├── stt.py               # wrapper faster-whisper
│   ├── llm.py                # wrapper Ollama/llama-cpp + prompt engineering (conversa + correção)
│   ├── tts.py                # wrapper Piper TTS
│   └── progress.py           # lógica de histórico/progresso (SQLite)
├── models/
│   └── db.py                  # schema SQLite
├── static/
│   └── (JS/CSS do frontend, gravação de áudio)
├── templates/
│   └── index.html             # interface principal
├── requirements.txt
└── README.md                  # instruções de setup, download de modelos, como rodar
```

### Requisitos não-funcionais
- O app deve funcionar **totalmente offline** após o setup inicial (download dos modelos).
- Deve incluir um **README detalhado** explicando: como instalar dependências, como baixar/configurar os modelos (Ollama pull, download do Piper voice, download do modelo Whisper), e como rodar o servidor (`uvicorn app.main:app`).
- Tratar **latência**: como tudo roda em CPU, a resposta não será instantânea — implemente indicadores visuais de "carregando/processando" no frontend para cada etapa (transcrevendo, pensando, gerando voz).
- Código modular, comentado, com tratamento de erros (ex: microfone não detectado, modelo não encontrado).
- Não usar nenhuma API externa paga ou que exija internet/chave de API.

### Entregáveis esperados
1. Código-fonte completo e funcional do app.
2. README com instruções de instalação e setup dos modelos (incluindo comandos exatos para Ollama e download das vozes Piper).
3. Um exemplo de prompt de sistema para o LLM que define a persona de "parceiro de conversação em inglês" com a lógica de correção de erros embutida na resposta (formato estruturado, ex: JSON com `reply`, `corrections`, `explanation`).
4. Instruções de como trocar facilmente o modelo LLM ou a voz do TTS por outro, caso o usuário queira testar alternativas.

Antes de começar a codificar, monte um plano resumido da arquitetura e confirme comigo as escolhas de modelos (tamanho, trade-off velocidade x qualidade) antes de implementar.
