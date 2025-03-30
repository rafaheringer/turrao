#!/usr/bin/env python3
"""
Turrão - Assistente Pessoal Conversacional
------------------------------------------

Aplicação principal que coordena o fluxo de processamento do assistente
usando a API Realtime da OpenAI para comunicação bidirecional de voz.

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
    from src.api.realtime_agent import RealtimeAgent
    from src.core.conversation_manager import ConversationManager
    from src.utils.config import load_config
except ImportError as e:
    logger.critical(f"Erro ao importar módulos: {e}")
    logger.info("Certifique-se de que todas as dependências estão instaladas e que o ambiente virtual está ativado.")
    sys.exit(1)

class TurraoAssistant:
    """
    Classe principal do assistente Turrão que coordena todos os componentes
    e implementa o loop principal de conversação usando a API Realtime.
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
            self.realtime_agent = RealtimeAgent(self.config["api"])
            self.conversation_manager = ConversationManager(
                realtime_agent=self.realtime_agent,
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
    
    async def on_speech_recognized(self, text: str) -> None:
        """
        Callback executado quando a fala do usuário é reconhecida.
        
        Args:
            text: Texto reconhecido da fala do usuário
        """
        logger.info(f"Usuário: {text}")
    
    async def on_response_text(self, text: str) -> None:
        """
        Callback executado quando texto da resposta é recebido.
        
        Args:
            text: Fragmento de texto da resposta
        """
        logger.info(f"Assistente: {text}")
    
    async def conversation_loop(self) -> None:
        """Loop principal de conversação assíncrona usando a API Realtime."""
        self.running = True
        
        # Mensagem de boas-vindas
        welcome_message = "Olá! Eu sou o Turrão, seu assistente pessoal. Como posso ajudar?"
        logger.info(f"Assistente: {welcome_message}")
        
        while self.running:
            try:
                logger.info("Iniciando sessão de conversação em tempo real...")
                
                # O ConversationManager agora gerencia o fluxo de conversação em tempo real
                await self.conversation_manager.start_realtime_conversation(
                    on_speech_recognized=self.on_speech_recognized,
                    on_response_text=self.on_response_text
                )
                
                # Aguardar um breve momento antes de reiniciar caso a sessão seja encerrada
                if self.running:
                    logger.info("Sessão de conversação encerrada, reiniciando em 2 segundos...")
                    await asyncio.sleep(2)
                
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                logger.error(f"Erro no loop de conversação: {e}")
                # Se ocorrer um erro, aguardar antes de continuar
                await asyncio.sleep(1)
    
    def start(self) -> None:
        """Inicia o assistente e o loop de conversação."""
        try:
            logger.info("Iniciando o assistente Turrão com API Realtime...")
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
