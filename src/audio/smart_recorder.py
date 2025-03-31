#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo para gravação inteligente de áudio.

Este módulo implementa um gravador que detecta automaticamente o início da fala e termina
a gravação quando detecta que o usuário parou de falar (silêncio), otimizando a experiência
de interação com o assistente.
"""

import time
import numpy as np
import pyaudio
import wave
import logging
import threading
import queue
from typing import Optional, List, Tuple, Callable

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes para captura de áudio
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Taxa de amostragem para captura
CHUNK_SIZE = 1024
SILENCE_THRESHOLD = 300  # Valor RMS para considerar como silêncio
SPEECH_THRESHOLD = 500   # Valor RMS para considerar como fala
MIN_SILENCE_DURATION = 1.0  # Segundos de silêncio para considerar que a fala terminou
MAX_SPEECH_DURATION = 15.0  # Duração máxima de gravação em segundos
MIN_SPEECH_DURATION = 1.0   # Duração mínima de gravação em segundos


class SmartRecorder:
    """
    Gravador inteligente que detecta o início e fim da fala automaticamente.
    """
    
    def __init__(self, 
                 silence_threshold: int = SILENCE_THRESHOLD,
                 speech_threshold: int = SPEECH_THRESHOLD,
                 sample_rate: int = RATE, 
                 min_silence_duration: float = MIN_SILENCE_DURATION,
                 max_speech_duration: float = MAX_SPEECH_DURATION,
                 min_speech_duration: float = MIN_SPEECH_DURATION,
                 channels: int = CHANNELS):
        """
        Inicializa o gravador inteligente.
        
        Args:
            silence_threshold: Valor RMS para considerar como silêncio
            speech_threshold: Valor RMS para considerar como fala
            sample_rate: Taxa de amostragem do áudio
            min_silence_duration: Duração mínima de silêncio para finalizar gravação
            max_speech_duration: Duração máxima de gravação
            min_speech_duration: Duração mínima de gravação
            channels: Número de canais de áudio (1=mono, 2=estéreo)
        """
        self.silence_threshold = silence_threshold
        self.speech_threshold = speech_threshold
        self.sample_rate = sample_rate
        self.min_silence_duration = min_silence_duration
        self.max_speech_duration = max_speech_duration
        self.min_speech_duration = min_speech_duration
        self.channels = channels
        
        self.is_recording = False
        self.stop_event = threading.Event()
        self.audio_data = []
        self.silent_chunks = 0
        self.record_thread = None
        self.audio = None
        self.stream = None
        
        # Controle de silêncio
        self.silence_start_time = 0
        self.recording_start_time = 0
        
        # Fila para dados de diagnóstico
        self.debug_queue = queue.Queue()
        
        # Armazenamento de calibração
        self.is_calibrated = False
        self.ambient_noise_level = 0
        
    def calibrate_microphone(self) -> float:
        """
        Calibra o microfone medindo o ruído ambiente.
        
        Returns:
            Nível de ruído ambiente detectado
        """
        if self.is_calibrated:
            logger.debug("Microfone já está calibrado.")
            return self.ambient_noise_level
            
        try:
            # Inicializar PyAudio temporariamente para calibração
            temp_audio = pyaudio.PyAudio()
            temp_stream = temp_audio.open(
                format=FORMAT,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            
            # Coletar amostras para calibração
            print("Calibrando... (silêncio, por favor)")
            ambient_noise = []
            for _ in range(10):  # Coletar 10 frames para calibração
                data = temp_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                ambient_noise.append(self._calculate_rms(audio_data))
                time.sleep(0.01)
            
            # Fechar recursos temporários
            temp_stream.stop_stream()
            temp_stream.close()
            temp_audio.terminate()
            
            # Calcular nível médio de ruído ambiente
            self.ambient_noise_level = np.mean(ambient_noise) if ambient_noise else 0
            
            # Ajustar os limiares com base no ruído ambiente
            self.silence_threshold = max(self.silence_threshold, self.ambient_noise_level * 1.5)
            self.speech_threshold = max(self.speech_threshold, self.ambient_noise_level * 2.5)
            
            print(f"Calibração concluída. Ruído ambiente: {self.ambient_noise_level:.1f}")
            self.is_calibrated = True
            
            return self.ambient_noise_level
            
        except Exception as e:
            logger.error(f"Erro durante a calibração do microfone: {e}")
            return 0
    
    def start_recording(self, callback: Optional[Callable[[bytes], None]] = None) -> None:
        """
        Inicia a gravação inteligente de áudio em um thread separado.
        
        Args:
            callback: Função chamada quando a gravação for concluída,
                     recebendo os dados de áudio como parâmetro
        """
        if self.is_recording:
            logger.warning("Gravação já está em andamento.")
            return
            
        self.stop_event.clear()
        self.audio_data = []
        self.silent_chunks = 0
        self.is_recording = True
        
        # Iniciar thread para gravação
        self.record_thread = threading.Thread(
            target=self._record_audio,
            args=(callback,)
        )
        self.record_thread.daemon = True
        self.record_thread.start()
        
        logger.info("Gravação inteligente iniciada. Aguardando fala...")
        
    def stop_recording(self) -> None:
        """
        Para a gravação de áudio.
        """
        if not self.is_recording:
            return
            
        self.stop_event.set()
        
        # Aguardar o término do thread (com timeout)
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=2.0)
            
        # Garantir que recursos sejam liberados
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            except Exception as e:
                logger.error(f"Erro ao fechar o stream: {e}")
                
        if self.audio:
            try:
                self.audio.terminate()
                self.audio = None
            except Exception as e:
                logger.error(f"Erro ao terminar o PyAudio: {e}")
                
        self.is_recording = False
        logger.info("Gravação inteligente interrompida.")
        
    def _calculate_rms(self, audio_data: np.ndarray) -> float:
        """
        Calcula o valor RMS (Root Mean Square) de um trecho de áudio.
        
        Args:
            audio_data: Array numpy com os dados de áudio
            
        Returns:
            Valor RMS calculado
        """
        audio_squared = np.square(audio_data.astype(np.float32))
        mean_squared = np.mean(audio_squared)
        
        # Evitar erro de raiz quadrada com números negativos
        if mean_squared > 0:
            rms = np.sqrt(mean_squared)
        else:
            rms = 0.0
            
        return rms
        
    def _record_audio(self, callback: Optional[Callable[[bytes], None]] = None) -> None:
        """
        Thread de gravação que monitora o áudio, detecta fala e silêncio.
        
        Args:
            callback: Função chamada quando a gravação for concluída
        """
        try:
            # Inicializar PyAudio
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=FORMAT,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            
            # Variáveis de controle
            is_speech_detected = False
            self.recording_start_time = 0
            self.silence_start_time = 0
            frames = []
            debug_info = {"rms_values": [], "timestamps": [], "states": []}
            
            # Calibração - usar a calibração existente ou fazer uma nova se necessário
            if not self.is_calibrated:
                self.calibrate_microphone()
            else:
                print(f"Usando calibração existente. Ruído ambiente: {self.ambient_noise_level:.1f}")
                
            print("Aguardando você falar... (fale normalmente)")
            
            # Loop principal de gravação
            while not self.stop_event.is_set():
                # Ler um chunk de áudio
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                # Calcular nível de áudio
                audio_data = np.frombuffer(data, dtype=np.int16)
                rms = self._calculate_rms(audio_data)
                
                # Adicionar dados de diagnóstico
                current_time = time.time()
                debug_info["rms_values"].append(rms)
                debug_info["timestamps"].append(current_time)
                
                # Verificar se é fala ou silêncio
                if rms > self.speech_threshold:
                    # Detectou fala
                    if not is_speech_detected:
                        # Início da fala detectado
                        is_speech_detected = True
                        self.recording_start_time = time.time()
                        print("Fala detectada! Gravando...")
                        debug_info["states"].append("START_SPEECH")
                    
                    # Resetar o contador de silêncio
                    self.silence_start_time = 0
                    self.silent_chunks = 0
                    
                    # Armazenar o frame
                    frames.append(data)
                    debug_info["states"].append("SPEECH")
                    
                elif is_speech_detected:
                    # Já estamos gravando, verificar se é silêncio
                    if rms < self.silence_threshold:
                        # É silêncio após fala
                        if self.silence_start_time == 0:
                            # Início do silêncio
                            self.silence_start_time = time.time()
                            debug_info["states"].append("START_SILENCE")
                        else:
                            # Continuação do silêncio
                            debug_info["states"].append("SILENCE")
                            
                        # Incrementar contador de silêncio
                        self.silent_chunks += 1
                        
                        # Verificar se já temos silêncio suficiente para parar
                        silence_duration = time.time() - self.silence_start_time
                        speech_duration = time.time() - self.recording_start_time
                        
                        if silence_duration >= self.min_silence_duration and speech_duration >= self.min_speech_duration:
                            # Silêncio suficiente detectado após fala mínima
                            print(f"Silêncio detectado após {speech_duration:.1f}s de fala. Finalizando gravação...")
                            break
                    else:
                        # Ainda é fala (ou ruído), mas abaixo do threshold de fala
                        self.silence_start_time = 0  # Resetar detecção de silêncio
                        debug_info["states"].append("WEAK_SPEECH")
                    
                    # Armazenar o frame mesmo durante o silêncio
                    frames.append(data)
                    
                    # Verificar se atingimos o tempo máximo de gravação
                    if time.time() - self.recording_start_time >= self.max_speech_duration:
                        print(f"Tempo máximo de gravação ({self.max_speech_duration}s) atingido. Finalizando...")
                        break
                else:
                    # Ainda estamos em modo de espera (sem fala detectada)
                    debug_info["states"].append("WAITING")
                
                # Pequena pausa para reduzir uso de CPU
                time.sleep(0.001)
            
            # Finalizar gravação
            self.stream.stop_stream()
            self.stream.close()
            self.audio.terminate()
            self.stream = None
            self.audio = None
            
            # Combinar todos os frames em um único buffer de áudio
            audio_buffer = b''.join(frames)
            
            # Calcular duração total
            total_duration = len(frames) * CHUNK_SIZE / self.sample_rate
            print(f"Gravação concluída. Duração: {total_duration:.2f}s")
            
            # Salvar dados de diagnóstico para debug
            self.debug_queue.put(debug_info)
            
            # Se não tem dados suficientes, não enviar
            if len(frames) < 3:  # Pelo menos 3 chunks (~60ms)
                print("Gravação muito curta. Ignorando.")
                return
                
            # Chamar o callback com os dados de áudio
            if callback:
                callback(audio_buffer)
            
        except Exception as e:
            logger.error(f"Erro na gravação de áudio: {e}")
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
                    
            self.is_recording = False
    
    def save_to_wav(self, filename: str, audio_data: bytes = None) -> None:
        """
        Salva os dados de áudio em um arquivo WAV.
        
        Args:
            filename: Nome do arquivo a ser criado
            audio_data: Dados de áudio a serem salvos. Se None, usa os dados da última gravação.
        """
        data = audio_data if audio_data is not None else b''.join(self.audio_data)
        
        if not data:
            logger.warning("Nenhum dado de áudio para salvar.")
            return
            
        try:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16 bits = 2 bytes
                wf.setframerate(self.sample_rate)
                wf.writeframes(data)
                
            logger.info(f"Áudio salvo em {filename}")
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo de áudio: {e}")
    
    def get_debug_info(self) -> dict:
        """
        Obtém informações de diagnóstico da última gravação.
        
        Returns:
            Dicionário com informações de diagnóstico
        """
        try:
            return self.debug_queue.get_nowait()
        except queue.Empty:
            return None


# Função de teste para demonstrar uso
def test_smart_recorder():
    """Função de teste para o gravador inteligente."""
    print("=== Teste do Gravador Inteligente ===")
    print("Fale algo e o gravador detectará automaticamente o início e fim da sua fala.")
    
    recorder = SmartRecorder()
    
    # Função de callback que será chamada quando a gravação terminar
    def on_recording_complete(audio_data):
        print(f"Gravação finalizada! {len(audio_data)} bytes capturados.")
        # Salvar em um arquivo de teste
        recorder.save_to_wav("teste_gravacao.wav", audio_data)
    
    # Iniciar gravação
    recorder.start_recording(on_recording_complete)
    
    try:
        # Aguardar até que o usuário pressione Enter para sair
        input("Pressione Enter para cancelar a gravação...\n")
    except KeyboardInterrupt:
        pass
    finally:
        # Parar gravação
        recorder.stop_recording()
    
    print("Teste concluído!")


if __name__ == "__main__":
    # Configurar logging para testes
    logging.basicConfig(level=logging.INFO)
    
    # Executar o teste
    test_smart_recorder()
