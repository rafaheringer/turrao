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
from typing import Optional, List, Deque
from collections import deque

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
        self.audio_buffer = bytearray()  # Buffer contínuo para armazenar áudio
        self.stop_flag = threading.Event()
        self.player_thread = None
        self.is_playing = False
        self.buffer_size = 8192  # Aumentar o tamanho do buffer para evitar cortes
        self.buffer_threshold = 0.1  # Segundos de áudio antes de iniciar (100ms)
        self.frame_count = 0
        self.stream = None  # Stream de áudio para reprodução contínua
        self.stream_lock = threading.Lock()
        self.buffer_ready = threading.Event()
        self.min_buffer_samples = int(sample_rate * 0.2)  # 200ms de buffer mínimo

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

    def _process_audio_buffer(self) -> None:
        """
        Processa a fila de áudio e mantém um buffer contínuo.
        """
        try:
            while not self.stop_flag.is_set():
                try:
                    # Obter próximo chunk (com timeout para verificar stop_flag regularmente)
                    audio_bytes = self.audio_queue.get(timeout=0.2)
                    
                    # Adicionar ao buffer contínuo
                    with self.stream_lock:
                        self.audio_buffer.extend(audio_bytes)
                    
                    # Sinalizar que o buffer está pronto se tiver dados suficientes
                    if len(self.audio_buffer) >= self.min_buffer_samples * 2:  # * 2 para contar bytes (16-bit = 2 bytes)
                        self.buffer_ready.set()
                    
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
            logger.error(f"Erro no processamento do buffer de áudio: {e}")

    def _stream_callback(self, outdata, frames, time, status):
        """
        Callback chamado pelo stream de áudio quando precisa de mais dados.
        
        Este método é crítico para a reprodução contínua sem cortes.
        """
        if status:
            logger.debug(f"Status do stream: {status}")
            
        # Adquirir o lock para acessar o buffer de áudio
        with self.stream_lock:
            # Número de bytes a ler (frames * channels * 2 bytes por amostra)
            bytes_to_read = frames * self.channels * 2
            
            if len(self.audio_buffer) >= bytes_to_read:
                # Temos dados suficientes no buffer
                data = self.audio_buffer[:bytes_to_read]
                self.audio_buffer = self.audio_buffer[bytes_to_read:]
                
                # Converter para numpy array
                audio_np = np.frombuffer(data, dtype=np.int16)
                
                # Copiar para a saída
                outdata[:] = audio_np.reshape(-1, self.channels)
            else:
                # Buffer underrun - preencher com silêncio
                outdata.fill(0)
                
                # Se não temos mais dados e a fila está vazia, sinalizar o fim da reprodução
                if self.audio_queue.empty() and (len(self.audio_buffer) < bytes_to_read):
                    # Se não há mais dados chegando e pedimos para parar
                    if self.stop_flag.is_set():
                        # Usar exceção especial para interromper o stream
                        raise sd.CallbackStop
                
                logger.debug(f"Buffer underrun: {len(self.audio_buffer)} bytes disponíveis, {bytes_to_read} bytes necessários")

    def _player_worker(self) -> None:
        """
        Worker thread que gerencia a reprodução contínua de áudio.
        """
        try:
            logger.debug("Thread de reprodução iniciada")
            
            # Iniciar a thread de processamento do buffer
            buffer_thread = threading.Thread(target=self._process_audio_buffer)
            buffer_thread.daemon = True
            buffer_thread.start()
            
            # Aguardar um pouco para acumular o buffer inicial
            buffer_start_time = time.time()
            buffer_timeout = 2.0  # 2 segundos no máximo para aguardar buffer
            
            # Aguardar até ter buffer suficiente ou timeout
            while not self.buffer_ready.is_set() and time.time() - buffer_start_time < buffer_timeout:
                if self.stop_flag.is_set():
                    return
                time.sleep(0.05)
            
            # Iniciar o stream de áudio
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='int16',
                callback=self._stream_callback,
                blocksize=1024  # Blocos menores para resposta mais rápida
            )
            
            # Iniciar a reprodução contínua
            self.stream.start()
            
            # Aguardar até que seja sinalizado para parar
            while not self.stop_flag.is_set() or not self.audio_queue.empty() or len(self.audio_buffer) > 0:
                time.sleep(0.1)
                
            # Garantir que o stream seja fechado adequadamente
            if self.stream and self.stream.active:
                self.stream.stop()
                self.stream.close()
                self.stream = None
                
            logger.debug("Thread de reprodução encerrada")
        except Exception as e:
            logger.error(f"Erro fatal na thread de reprodução: {e}")
        finally:
            self.is_playing = False
            # Fechar o stream se ainda estiver aberto
            if self.stream and self.stream.active:
                self.stream.stop()
                self.stream.close()
                self.stream = None

    def start_playback(self) -> None:
        """
        Inicia a thread de reprodução de áudio.
        """
        if self.is_playing:
            return
            
        # Resetar a flag de parada
        self.stop_flag.clear()
        self.buffer_ready.clear()
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
            self.player_thread.join(timeout=0.1)
        
        # Fechar o stream se necessário
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        # Limpar a fila
        with self.stream_lock:
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.task_done()
                except queue.Empty:
                    break
            
            # Limpar o buffer
            self.audio_buffer.clear()
        
        self.is_playing = False

    def reset_frame_count(self) -> None:
        """
        Reseta o contador de frames (útil para novas sessões).
        """
        self.frame_count = 0

    def is_buffer_empty(self) -> bool:
        """
        Verifica se o buffer de áudio está vazio e a reprodução terminou.
        
        Returns:
            True se o buffer estiver vazio e não há mais reprodução, False caso contrário
        """
        # Se a fila estiver vazia, o buffer estiver quase vazio e o stream não estiver ativo
        # ou não tivermos mais do que uma pequena quantidade de dados, consideramos que terminou
        buffer_threshold = 100  # Consideramos vazio se tiver menos que 100 bytes 
        
        if self.audio_queue.empty() and len(self.audio_buffer) < buffer_threshold:
            if self.stream is None or not self.stream.active:
                return True
            
            # Se tivermos um stream ativo mas quase sem dados, vamos verificar um pouco mais
            # profundamente se ainda há reprodução acontecendo
            if len(self.audio_buffer) == 0:
                return True
                
        return False
        
    def is_playing_complete(self) -> bool:
        """
        Método mais confiável para verificar se a reprodução foi concluída.
        
        Este método faz uma verificação mais profunda do que is_buffer_empty().
        
        Returns:
            True se a reprodução estiver concluída, False caso contrário
        """
        # Considerar concluído quando:
        # 1. A fila de entrada está vazia (não chegará mais dados)
        # 2. O buffer tem poucos dados restantes (menos que X ms de áudio)
        # 3. O stream não está ativo OU está prestes a terminar
        
        buffer_almost_empty = len(self.audio_buffer) < (self.sample_rate * 0.1)  # Menos de 100ms de áudio
        stream_inactive = self.stream is None or not self.stream.active
        
        return (self.audio_queue.empty() and 
                (buffer_almost_empty or stream_inactive) and
                (self.frame_count > 0))  # Garantir que pelo menos um frame foi processado

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
