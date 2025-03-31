#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo para reprodução de áudio em tempo real.

Este módulo implementa um reprodutor de áudio que consegue tocar os 
chunks de áudio à medida que são recebidos da API, sem precisar esperar
por todo o conteúdo para iniciar a reprodução.
"""

import logging
import threading
import queue
import time
import numpy as np
import sounddevice as sd
from typing import Optional, List

# Configurar logger
logger = logging.getLogger(__name__)


class AudioPlayerRealtime:
    """
    Reprodutor de áudio em tempo real que utiliza threads para processamento
    contínuo de chunks de áudio.
    """

    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        """
        Inicializa o reprodutor de áudio em tempo real.
        
        Args:
            sample_rate: Taxa de amostragem do áudio (padrão: 24kHz para API da OpenAI)
            channels: Número de canais de áudio (mono = 1, estéreo = 2)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.player_thread = None
        self.is_playing = False
        self.buffer_size = 4096  # Tamanho do buffer para reprodução
        self.silence_threshold = 0.1  # Segundos de silêncio antes de iniciar reprodução
        self.silence_buffer: List[bytes] = []
        self.frame_count = 0

    def add_audio_chunk(self, audio_bytes: bytes) -> None:
        """
        Adiciona um chunk de áudio à fila de reprodução.
        
        Args:
            audio_bytes: Dados de áudio em bytes
        """
        if not audio_bytes:
            return
        
        # Adicionar o chunk à fila
        self.audio_queue.put(audio_bytes)
        
        # Iniciar o thread de reprodução se ainda não estiver rodando
        if not self.is_playing:
            self.start_playback()

    def _player_worker(self) -> None:
        """
        Worker thread que reproduz os chunks de áudio à medida que ficam disponíveis.
        """
        try:
            logger.debug("Thread de reprodução iniciada")
            
            # Aguardar um pouco para acumular alguns chunks iniciais
            # e evitar cortes no início da reprodução
            initial_buffer_time = 0.2  # 200ms de buffer inicial
            buffering_started = time.time()
            
            # Aguardar até ter dados suficientes ou timeout
            while (time.time() - buffering_started < initial_buffer_time and 
                   self.audio_queue.qsize() < 3 and 
                   not self.stop_flag.is_set()):
                time.sleep(0.05)
            
            # Loop principal de reprodução
            while not self.stop_flag.is_set():
                try:
                    # Obter próximo chunk (com timeout para verificar stop_flag regularmente)
                    audio_bytes = self.audio_queue.get(timeout=0.5)
                    
                    # Converter bytes para array numpy
                    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                    
                    # Reproduzir o áudio
                    sd.play(audio_np, samplerate=self.sample_rate)
                    sd.wait()  # Aguardar a conclusão da reprodução
                    
                    # Marcar como concluído
                    self.audio_queue.task_done()
                    
                    # Incrementar contador de frames
                    self.frame_count += 1
                    
                except queue.Empty:
                    # Fila vazia, verificar se devemos parar
                    if self.audio_queue.empty() and self.stop_flag.is_set():
                        break
                    # Caso contrário, continuar verificando a fila
                    continue
                except Exception as e:
                    logger.error(f"Erro na reprodução de áudio: {e}")
                    continue
                    
            logger.debug("Thread de reprodução encerrada")
        except Exception as e:
            logger.error(f"Erro fatal na thread de reprodução: {e}")
        finally:
            self.is_playing = False

    def start_playback(self) -> None:
        """
        Inicia a thread de reprodução de áudio.
        """
        if self.is_playing:
            return
            
        # Resetar a flag de parada
        self.stop_flag.clear()
        self.is_playing = True
        
        # Iniciar thread de reprodução
        self.player_thread = threading.Thread(target=self._player_worker)
        self.player_thread.daemon = True  # Thread em background
        self.player_thread.start()

    def stop_playback(self) -> None:
        """
        Para a reprodução de áudio e limpa a fila.
        """
        if not self.is_playing:
            return
            
        # Sinalizar para a thread parar
        self.stop_flag.set()
        
        # Aguardar a thread terminar (com timeout)
        if self.player_thread and self.player_thread.is_alive():
            self.player_thread.join(timeout=1.0)
        
        # Limpar a fila
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except queue.Empty:
                break
        
        self.is_playing = False

    def reset_frame_count(self) -> None:
        """
        Reseta o contador de frames (útil para novas sessões).
        """
        self.frame_count = 0

    def is_buffer_empty(self) -> bool:
        """
        Verifica se o buffer de áudio está vazio.
        
        Returns:
            True se o buffer estiver vazio, False caso contrário
        """
        return self.audio_queue.empty()

    def get_buffer_size(self) -> int:
        """
        Retorna o número de chunks no buffer.
        
        Returns:
            Número de chunks no buffer
        """
        return self.audio_queue.qsize()

    def __del__(self) -> None:
        """
        Destrutor que garante que a reprodução seja interrompida.
        """
        self.stop_playback()
