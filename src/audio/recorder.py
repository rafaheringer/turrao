"""
Módulo para captura de áudio através do microfone.

Este módulo implementa a funcionalidade de gravação de áudio do microfone
usando PyAudio ou outras bibliotecas de áudio conforme configurado.
"""

import asyncio
import io
from typing import Any, Dict, Optional

import numpy as np

# Importação condicional para PyAudio
try:
    import pyaudio
    import wave
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioRecorder:
    """
    Classe para gravação de áudio do microfone.
    
    Implementa a funcionalidade de captura de áudio usando PyAudio,
    com suporte para detecção de silêncio e gravação contínua ou por comando.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o gravador de áudio com as configurações especificadas.
        
        Args:
            config: Dicionário com configurações de áudio
        
        Raises:
            ImportError: Se PyAudio não estiver instalado
            RuntimeError: Se ocorrer erro na inicialização do PyAudio
        """
        if not HAS_PYAUDIO:
            logger.critical("PyAudio não está instalado. A captura de áudio não funcionará.")
            raise ImportError("PyAudio é necessário para captura de áudio")
        
        self.config = config
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.chunk_size = config.get("chunk_size", 1024)
        
        # Mapeamento de formatos de áudio para PyAudio
        format_map = {
            "Int8": pyaudio.paInt8,
            "Int16": pyaudio.paInt16,
            "Int32": pyaudio.paInt32,
            "Float32": pyaudio.paFloat32
        }
        format_str = config.get("format", "Int16")
        self.format = format_map.get(format_str, pyaudio.paInt16)
        
        # Configuração para detecção de silêncio
        self.silence_threshold = config.get("silence_threshold", 700)  # Valor padrão para formato Int16
        self.silence_duration = config.get("silence_duration", 1.0)  # Segundos
        
        # Inicialização do PyAudio
        try:
            self.pa = pyaudio.PyAudio()
            self.stream = None
            logger.debug("AudioRecorder inicializado com sucesso")
        except Exception as e:
            logger.critical(f"Erro ao inicializar PyAudio: {e}")
            raise RuntimeError(f"Falha na inicialização do PyAudio: {e}")
    
    def _open_stream(self) -> None:
        """
        Abre o stream de áudio para gravação.
        
        Raises:
            RuntimeError: Se ocorrer erro ao abrir o stream
        """
        if self.stream and self.stream.is_active():
            return
            
        try:
            self.stream = self.pa.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            logger.debug("Stream de áudio aberto para gravação")
        except Exception as e:
            logger.error(f"Erro ao abrir stream de áudio: {e}")
            raise RuntimeError(f"Falha ao abrir stream de áudio: {e}")
    
    def _close_stream(self) -> None:
        """Fecha o stream de áudio se estiver aberto."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            logger.debug("Stream de áudio fechado")
    
    async def record(self, duration: Optional[float] = None) -> bytes:
        """
        Grava áudio do microfone até detectar silêncio ou atingir a duração máxima.
        
        Args:
            duration: Duração máxima da gravação em segundos (None para usar detecção de silêncio)
        
        Returns:
            Dados de áudio gravados como bytes
        
        Raises:
            RuntimeError: Se ocorrer erro durante a gravação
        """
        try:
            self._open_stream()
            
            frames = []
            silence_frames = 0
            max_frames = int(self.sample_rate / self.chunk_size * (duration or 60))  # Limite de 60s se duração não especificada
            silence_limit = int(self.silence_duration * self.sample_rate / self.chunk_size)
            
            # Aviso de início da gravação
            logger.info("Gravando... (fale agora)")
            
            # Remover ruído inicial (500ms)
            for _ in range(int(0.5 * self.sample_rate / self.chunk_size)):
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                await asyncio.sleep(0)  # Yield para o event loop
            
            # Esperar por algum som que não seja silêncio para começar a gravar de verdade
            is_speaking = False
            timeout = 100  # Aproximadamente 10 segundos de espera (100 * chunk_size / sample_rate)
            
            for _ in range(timeout):
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                if self._is_above_threshold(data):
                    is_speaking = True
                    frames.append(data)
                    break
                await asyncio.sleep(0.01)  # Pequeno delay para não sobrecarregar a CPU
            
            if not is_speaking:
                logger.info("Nenhum áudio detectado, encerrando gravação")
                return b""
            
            # Continuar gravando até detectar silêncio ou atingir duração máxima
            for _ in range(max_frames):
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
                
                # Verificar silêncio
                if not self._is_above_threshold(data):
                    silence_frames += 1
                    if silence_frames >= silence_limit:
                        break
                else:
                    silence_frames = 0
                
                # Yield para o event loop a cada poucos frames para manter responsividade
                if len(frames) % 10 == 0:
                    await asyncio.sleep(0)
            
            logger.info("Gravação concluída")
            
            # Combinar todos os frames em um único buffer de áudio
            audio_data = b"".join(frames)
            return audio_data
            
        except Exception as e:
            logger.error(f"Erro durante a gravação: {e}")
            raise RuntimeError(f"Falha na gravação de áudio: {e}")
    
    def _is_above_threshold(self, data: bytes) -> bool:
        """
        Verifica se o nível de áudio está acima do limiar de silêncio.
        
        Args:
            data: Dados de áudio a serem verificados
        
        Returns:
            True se o áudio estiver acima do limiar de silêncio
        """
        # Converter bytes para array numpy dependendo do formato
        if self.format == pyaudio.paInt16:
            audio_array = np.frombuffer(data, dtype=np.int16)
        elif self.format == pyaudio.paInt32:
            audio_array = np.frombuffer(data, dtype=np.int32)
        elif self.format == pyaudio.paFloat32:
            audio_array = np.frombuffer(data, dtype=np.float32)
        else:  # Int8
            audio_array = np.frombuffer(data, dtype=np.int8)
        
        # Calcular o valor RMS (root mean square)
        rms = np.sqrt(np.mean(np.square(audio_array)))
        return rms > self.silence_threshold
    
    def save_to_file(self, audio_data: bytes, filename: str) -> None:
        """
        Salva os dados de áudio em um arquivo WAV.
        
        Args:
            audio_data: Dados de áudio a serem salvos
            filename: Nome do arquivo de saída
        
        Raises:
            IOError: Se ocorrer erro ao salvar o arquivo
        """
        try:
            with wave.open(filename, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pa.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data)
            
            logger.debug(f"Áudio salvo em {filename}")
        except Exception as e:
            logger.error(f"Erro ao salvar áudio em {filename}: {e}")
            raise IOError(f"Falha ao salvar arquivo de áudio: {e}")
    
    def close(self) -> None:
        """Fecha o gravador de áudio e libera recursos."""
        self._close_stream()
        if self.pa:
            self.pa.terminate()
            logger.debug("PyAudio encerrado")
