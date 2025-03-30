# Nome do Projeto: Turrão

## Objetivo Geral

Desenvolver um dispositivo IoT conversacional, inspirado em assistentes pessoais como a Alexa, utilizando as APIs do ChatGPT para proporcionar interações em tempo real. O projeto será dividido em duas fases principais:

1. **Prova de Conceito (POC) em Software:**  
   - Simular o fluxo completo de conversação, desde a captura de áudio, conversão de áudio para texto (STT), processamento da conversa via API do ChatGPT e a conversão do texto de resposta em áudio (TTS).

2. **Implementação no Hardware (Raspberry Pi):**  
   - Adaptar e integrar a solução de software ao Raspberry Pi, utilizando dispositivos de entrada e saída de áudio (microfone e alto-falante), para validar a performance e a usabilidade em um ambiente real.

## Prompt Inicial para a AI

Você é o Turrão, um assistente pessoal com personalidade forte, irreverente e um humor ácido. Notoriamente turrão e teimoso, você não hesita em responder com sarcasmo e ironia, arrancando risadas mesmo quando sua resposta é direta. Sua missão é ajudar o usuário de forma assertiva, mas sempre com um toque de humor picante, que reflete seu temperamento único e ácido. Use seu humor para tornar a experiência interativa divertida.

## Estrutura do Projeto

```
/src
  /audio      - Módulos de captura e processamento de áudio
  /stt        - Conversão de fala para texto
  /tts        - Conversão de texto para fala
  /api        - Integrações com API do ChatGPT
  /core       - Lógica principal do assistente
  /utils      - Utilitários e ferramentas comuns
  /config     - Arquivos de configuração
/tests        - Testes unitários e de integração
/docs         - Documentação do projeto
/scripts      - Scripts de automação
```

## Requisitos

Este projeto requer Python 3.12+ e as seguintes bibliotecas principais:
- PyAudio - Para captura e reprodução de áudio
- SpeechRecognition - Para conversão de fala para texto
- gTTS/pyttsx3 - Para conversão de texto para fala
- openai - SDK para integração com a API do ChatGPT
- Outras dependências listadas em `requirements.txt`

## Configuração do Ambiente

1. Clone o repositório:
   ```
   git clone https://github.com/rafaheringer/turrao
   cd turrao
   ```

2. Crie e ative um ambiente virtual:
   ```
   python -m venv .venv
   # No Windows
   .venv\Scripts\activate
   # No Linux/Mac
   source .venv/bin/activate
   ```

3. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente:
   - Crie um arquivo `.env` baseado no `.env.example`
   - Adicione sua chave de API do OpenAI

## Uso

Para iniciar o assistente Turrão:
```
python -m src.main
```

## Contribuição

Este é um projeto open source e contribuições são bem-vindas. Veja o arquivo CONTRIBUTING.md para mais detalhes.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para mais detalhes.