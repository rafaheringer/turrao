#!/usr/bin/env python3
"""
Turrão - Assistente Pessoal Conversacional
------------------------------------------

Aplicação principal que coordena o fluxo de processamento do assistente:
1. Captura de áudio do microfone
2. Conversão de áudio para texto (STT)
3. Processamento do texto pela API do ChatGPT
4. Conversão da resposta de texto para áudio (TTS)
5. Reprodução do áudio para o usuário

Este módulo implementa o ponto de entrada da aplicação e o loop principal de execução.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Any, Dict, Optional

# Configuração de logging antes de qualquer import
from src.utils.logger import setup_logger
logger = setup_logger()

try:
    # Importações internas do projeto
    from src.audio.recorder import AudioRecorder
    from src.audio.player import AudioPlayer
    from src.stt.speech_to_text import SpeechToText
    from src.tts.text_to_speech import TextToSpeech
    from src.api.openai_client import OpenAIClient
    from src.core.conversation_manager import ConversationManager
    from src.utils.config import load_config
except ImportError as e:
    logger.critical(f"Erro ao importar módulos: {e}")
    logger.info("Certifique-se de que todas as dependências estão instaladas e que o ambiente virtual está ativado.")
    sys.exit(1)

class TurraoAssistant:
    """
    Classe principal do assistente Turrão que coordena todos os componentes
    e implementa o loop principal de conversação.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Inicializa o assistente Turrão, carregando configurações e instanciando componentes.
        
        Args:
            config_path: Caminho opcional para o arquivo de configuração.
        """
        self.config = load_config(config_path)
        self.running = False
        
        # Inicialização dos componentes
        self._initialize_components()
        
        # Configuração dos handlers para signals (Ctrl+C)
        self._setup_signal_handlers()
        
        logger.info("Turrão inicializado e pronto para conversar!")
    
    def _initialize_components(self) -> None:
        """Inicializa todos os componentes do assistente."""
        try:
            self.audio_recorder = AudioRecorder(self.config["audio"])
            self.audio_player = AudioPlayer(self.config["audio"])
            self.stt = SpeechToText(self.config["stt"])
            self.tts = TextToSpeech(self.config["tts"])
            self.openai_client = OpenAIClient(self.config["api"])
            self.conversation_manager = ConversationManager(
                openai_client=self.openai_client,
                config=self.config["assistant"]
            )
            logger.debug("Todos os componentes foram inicializados com sucesso")
        except Exception as e:
            logger.critical(f"Erro ao inicializar componentes: {e}")
            raise
    
    def _setup_signal_handlers(self) -> None:
        """Configura manipuladores de sinais para encerramento adequado."""
        signals = [signal.SIGINT, signal.SIGTERM]
        for sig in signals:
            signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, sig: Any, frame: Any) -> None:
        """
        Manipulador de sinais para encerramento limpo.
        
        Args:
            sig: Sinal recebido
            frame: Frame atual
        """
        logger.info(f"Sinal {sig} recebido, encerrando...")
        self.stop()
    
    async def conversation_loop(self) -> None:
        """Loop principal de conversação assíncrona."""
        self.running = True
        
        # Mensagem de boas-vindas
        welcome_message = "Olá! Eu sou o Turrão, seu assistente pessoal. Como posso ajudar?"
        logger.info(f"Assistente: {welcome_message}")
        
        # Convertendo boas-vindas em áudio e reproduzindo
        welcome_audio = await self.tts.synthesize(welcome_message)
        await self.audio_player.play(welcome_audio)
        
        while self.running:
            try:
                logger.info("Aguardando comando de voz...")
                
                # Captura de áudio
                audio_data = await self.audio_recorder.record()
                
                # Conversão para texto
                text = await self.stt.transcribe(audio_data)
                if not text:
                    logger.debug("Nenhum texto reconhecido, continuando...")
                    continue
                
                logger.info(f"Usuário: {text}")
                
                # Processamento pela API do ChatGPT
                response = await self.conversation_manager.process_input(text)
                logger.info(f"Assistente: {response}")
                
                # Conversão para áudio e reprodução
                response_audio = await self.tts.synthesize(response)
                await self.audio_player.play(response_audio)
                
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                logger.error(f"Erro no loop de conversação: {e}")
                # Se ocorrer um erro, aguardar antes de continuar
                await asyncio.sleep(1)
    
    def start(self) -> None:
        """Inicia o assistente e o loop de conversação."""
        try:
            logger.info("Iniciando o assistente Turrão...")
            asyncio.run(self.conversation_loop())
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Encerra o assistente e libera recursos."""
        if not self.running:
            return
            
        logger.info("Encerrando o assistente Turrão...")
        self.running = False
        
        # Liberação de recursos
        self.audio_recorder.close()
        self.audio_player.close()
        
        logger.info("Assistente encerrado. Até mais!")


def main() -> None:
    """Função principal que inicia o assistente."""
    try:
        assistant = TurraoAssistant()
        assistant.start()
    except Exception as e:
        logger.critical(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
