# Projeto IoT: Dispositivo Conversacional (Estilo Alexa)

## 1. Definição do Projeto e Requisitos
- [x] **Objetivo Geral:** Criar um dispositivo IoT com capacidades de conversação usando a API do ChatGPT em tempo real.
- [x] **Escopo do POC:** Desenvolver uma prova de conceito apenas com software, simulando a integração do fluxo de áudio.
- [x] **Requisitos Funcionais:**
  - Captura de áudio (entrada do usuário)
  - Conversão de áudio para texto (speech-to-text)
  - Envio do texto para a API do ChatGPT e recepção da resposta
  - Conversão do texto de resposta em áudio (text-to-speech)
  - Reprodução do áudio para o usuário
- [x] **Requisitos Não Funcionais:**
  - Latência aceitável na conversação
  - Robustez e tratamento de erros na comunicação com APIs
  - Facilidade de escalabilidade para a integração com hardware

## 2. Configuração do Ambiente de Desenvolvimento (Software)
- [x] Escolher a linguagem e frameworks (ex.: Python, Flask, etc.)
- [x] Configurar ambiente virtual e gerenciador de dependências (ex.: venv, pipenv)
- [x] Instalar bibliotecas necessárias:
  - Para captura e reprodução de áudio (ex.: PyAudio)
  - Para comunicação HTTP (ex.: requests ou httpx)
  - Para conversão de áudio (ex.: integração com serviços de STT/TTS)
- [x] Definir a arquitetura do sistema (módulos de áudio, API, lógica de conversação)

## 3. Integração com API do ChatGPT e Realtime Áudio
- [ ] **Acesso às APIs:**
  - Confirmar acesso à API do ChatGPT com suporte para realtime áudio (ou simular a integração)
- [ ] **Módulo de Áudio:**
  - [ ] Captura de áudio do microfone
  - [ ] Processamento do áudio para envio à API (se necessário, realizar pré-processamento)
- [ ] **Conversão de Áudio para Texto (STT):**
  - [ ] Integrar ou desenvolver um módulo de Speech-to-Text
  - [ ] Testar precisão e latência da conversão
- [ ] **Integração com ChatGPT:**
  - [ ] Enviar o texto obtido para a API do ChatGPT
  - [ ] Processar e armazenar a resposta
- [ ] **Conversão de Texto para Áudio (TTS):**
  - [ ] Integrar ou desenvolver um módulo de Text-to-Speech
  - [ ] Testar a reprodução do áudio gerado
- [ ] **Fluxo Completo de Conversação:**
  - [ ] Desenvolver e testar o fluxo de ponta a ponta: captura → STT → ChatGPT → TTS → reprodução

## 4. Testes do Software
- [ ] Criar casos de teste para cada módulo (STT, API ChatGPT, TTS)
- [ ] Testar a integração entre os módulos
- [ ] Monitorar latência e desempenho do fluxo completo
- [ ] Implementar tratamento de erros e logs para debugging

## 5. Preparação para Integração com Hardware (Raspberry Pi)
- [ ] **Configuração do Raspberry Pi:**
  - [ ] Instalar e configurar o sistema operacional (ex.: Raspberry Pi OS)
  - [ ] Configurar rede e acesso remoto (SSH)
- [ ] **Hardware de Áudio:**
  - [ ] Testar e configurar microfone e alto-falante
  - [ ] Validar a compatibilidade dos dispositivos com o Pi
- [ ] **Portabilidade do Software:**
  - [ ] Adaptar o código da POC para o ambiente do Raspberry Pi
  - [ ] Realizar testes de desempenho no hardware embarcado

## 6. Validação e Iteração
- [ ] Coletar feedback dos testes (simulados e em hardware)
- [ ] Identificar e priorizar melhorias e correções
- [ ] Atualizar a documentação e checklist conforme necessário

## 7. Documentação e Roadmap Final
- [ ] Documentar a arquitetura e o fluxo de dados
- [ ] Registrar configurações e dependências utilizadas
- [ ] Planejar etapas futuras para a produção final do dispositivo