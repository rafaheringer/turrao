#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo para detecção de voz em tempo real.

Este módulo implementa um detector de voz que monitora continuamente
o áudio do microfone e detecta quando há atividade de voz, iniciando
automaticamente a gravação quando alguém começa a falar.
"""

import numpy as np
import pyaudio
import time
import logging
import asyncio
import threading
from typing import Optional, Callable

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes para captura de áudio
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Taxa de amostragem para detecção (16kHz é suficiente)
CHUNK_SIZE = 1024
SILENCE_THRESHOLD = 300  # Reduzido para melhor sensibilidade
SILENCE_FRAMES = 20  # Quantos frames silenciosos para considerar como silêncio contínuo


class VoiceDetector:
    """
    Detector de voz que monitora o microfone e identifica quando alguém começa a falar.
    """
    
    def __init__(self, 
                 threshold: int = SILENCE_THRESHOLD,
                 sample_rate: int = RATE, 
                 chunk_size: int = CHUNK_SIZE):
        """
        Inicializa o detector de voz.
        
        Args:
            threshold: Valor de amplitude para considerar como voz (padrão: 300)
            sample_rate: Taxa de amostragem do áudio
            chunk_size: Tamanho do chunk de áudio a ser processado por vez
        """
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.is_running = False
        self.stop_event = threading.Event()
        self.voice_detected_callback = None
        self.audio = None
        self.stream = None
        
    def start_monitoring(self, callback: Optional[Callable] = None) -> None:
        """
        Inicia o monitoramento do microfone em um thread separado.
        
        Args:
            callback: Função de callback chamada quando uma voz é detectada
        """
        if self.is_running:
            logger.warning("Detector de voz já está em execução.")
            return
            
        self.voice_detected_callback = callback
        self.stop_event.clear()
        self.is_running = True
        
        # Iniciar thread para monitoramento contínuo
        self.monitor_thread = threading.Thread(target=self._monitor_audio)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        logger.info("Detector de voz iniciado. Aguardando atividade de voz...")
        
    def stop_monitoring(self) -> None:
        """
        Para o monitoramento do microfone.
        """
        if not self.is_running:
            return
            
        self.stop_event.set()
        
        # Aguardar o término do thread (com timeout)
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
            
        # Garantir que o stream e PyAudio sejam fechados
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Erro ao fechar o stream: {e}")
                
        if self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                logger.error(f"Erro ao terminar o PyAudio: {e}")
                
        self.is_running = False
        logger.info("Detector de voz parado.")
        
    def _monitor_audio(self) -> None:
        """
        Método privado que monitora continuamente o microfone.
        """
        try:
            # Inicializar PyAudio
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            # Contadores para detecção
            silent_frames = 0
            is_speaking = False
            
            # Loop principal de monitoramento
            while not self.stop_event.is_set():
                # Ler dados do microfone
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                # Converter para array numpy
                audio_data = np.frombuffer(data, dtype=np.int16)
                
                # Calcular o valor RMS (raiz quadrada da média dos quadrados)
                # como medida da intensidade do áudio
                audio_squared = np.square(audio_data.astype(np.float32))
                mean_squared = np.mean(audio_squared)
                
                # Evitar erro de raiz quadrada com números negativos
                if mean_squared > 0:
                    rms = np.sqrt(mean_squared)
                else:
                    rms = 0.0
                
                # Detectar se há voz
                if rms > self.threshold:
                    # Reiniciar contador de frames silenciosos
                    silent_frames = 0
                    
                    # Se não estava falando antes, sinalizar início de fala
                    if not is_speaking:
                        is_speaking = True
                        logger.debug(f"Voz detectada! (RMS: {rms:.1f})")
                        
                        # Notificar através do callback
                        if self.voice_detected_callback:
                            self.voice_detected_callback()
                            
                            # Após callback ser chamado, pausamos a detecção por um tempo
                            # para evitar múltiplas detecções durante a gravação
                            time.sleep(7)  # Pausa após detecção (tempo de gravação + margem)
                            is_speaking = False
                else:
                    # Incrementar contador de frames silenciosos
                    silent_frames += 1
                    
                    # Se tiver muitos frames silenciosos seguidos, resetar o estado
                    if silent_frames > SILENCE_FRAMES:
                        is_speaking = False
                
                # Pequena pausa para evitar uso excessivo de CPU
                time.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Erro no monitoramento de áudio: {e}")
        finally:
            # Garantir limpeza dos recursos
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except:
                    pass
                    
            if self.audio:
                try:
                    self.audio.terminate()
                except:
                    pass
                    
            self.is_running = False


# Função auxiliar para criar e gerenciar o detector
async def listen_for_voice(callback: Callable) -> None:
    """
    Inicia o detector de voz e aguarda por atividade de voz.
    
    Args:
        callback: Função a ser chamada quando uma voz for detectada
    """
    detector = VoiceDetector()
    
    try:
        detector.start_monitoring(callback)
        
        # Manter o detector rodando
        while True:
            # Verificar periodicamente se deve continuar
            await asyncio.sleep(0.5)
            if not detector.is_running:
                break
                
    except asyncio.CancelledError:
        detector.stop_monitoring()
    finally:
        detector.stop_monitoring()


# Função de teste para demonstrar uso
async def test_voice_detection():
    """Função de teste para o detector de voz."""
    print("Teste de detecção de voz")
    print("Fale algo para ativar o detector...")
    
    # Função de callback que será chamada quando uma voz for detectada
    def on_voice_detected():
        print("\nVoz detectada! Iniciando gravação...")
    
    # Iniciar detector
    await listen_for_voice(on_voice_detected)


if __name__ == "__main__":
    # Testar o detector
    asyncio.run(test_voice_detection())
