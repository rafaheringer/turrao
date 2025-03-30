"""
Módulo para reprodução de áudio através dos alto-falantes.

Este módulo implementa a funcionalidade de reprodução de áudio usando PyAudio
ou outras bibliotecas de áudio conforme configurado.
"""

import asyncio
import io
from typing import Any, Dict, Optional, Union

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


class AudioPlayer:
    """
    Classe para reprodução de áudio através dos alto-falantes.
    
    Implementa a funcionalidade de reprodução de áudio usando PyAudio,
    suportando diferentes formatos e taxas de amostragem.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o reprodutor de áudio com as configurações especificadas.
        
        Args:
            config: Dicionário com configurações de áudio
        
        Raises:
            ImportError: Se PyAudio não estiver instalado
            RuntimeError: Se ocorrer erro na inicialização do PyAudio
        """
        if not HAS_PYAUDIO:
            logger.critical("PyAudio não está instalado. A reprodução de áudio não funcionará.")
            raise ImportError("PyAudio é necessário para reprodução de áudio")
        
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
        
        # Inicialização do PyAudio
        try:
            self.pa = pyaudio.PyAudio()
            self.stream = None
            logger.debug("AudioPlayer inicializado com sucesso")
        except Exception as e:
            logger.critical(f"Erro ao inicializar PyAudio: {e}")
            raise RuntimeError(f"Falha na inicialização do PyAudio: {e}")
    
    def _open_stream(self) -> None:
        """
        Abre o stream de áudio para reprodução.
        
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
                output=True,
                frames_per_buffer=self.chunk_size
            )
            logger.debug("Stream de áudio aberto para reprodução")
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
    
    async def play(self, audio_data: Union[bytes, str]) -> None:
        """
        Reproduz dados de áudio ou um arquivo de áudio.
        
        Args:
            audio_data: Dados de áudio como bytes ou caminho para um arquivo de áudio
        
        Raises:
            RuntimeError: Se ocorrer erro durante a reprodução
            ValueError: Se o formato de entrada for inválido
        """
        try:
            self._open_stream()
            
            # Verificar se audio_data é um caminho para arquivo
            if isinstance(audio_data, str):
                await self._play_file(audio_data)
            else:
                await self._play_bytes(audio_data)
                
        except Exception as e:
            logger.error(f"Erro durante a reprodução de áudio: {e}")
            raise RuntimeError(f"Falha na reprodução de áudio: {e}")
    
    async def _play_bytes(self, audio_data: bytes) -> None:
        """
        Reproduz dados de áudio em formato de bytes.
        
        Args:
            audio_data: Dados de áudio em formato de bytes
        """
        # Criar buffer de memória com os dados
        buffer = io.BytesIO(audio_data)
        
        # Tentar reproduzir como WAV primeiro
        try:
            with wave.open(buffer, "rb") as wf:
                # Obter parâmetros do arquivo WAV
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                framerate = wf.getframerate()
                
                # Reconfigurar o stream se necessário
                if channels != self.channels or framerate != self.sample_rate:
                    self._close_stream()
                    self.channels = channels
                    self.sample_rate = framerate
                    self._open_stream()
                
                # Leitura e reprodução dos dados
                data = wf.readframes(self.chunk_size)
                while len(data) > 0:
                    self.stream.write(data)
                    data = wf.readframes(self.chunk_size)
                    await asyncio.sleep(0)  # Yield para o event loop
                    
                return
        except Exception as e:
            # Não é um arquivo WAV válido, tentar reproduzir como raw PCM
            logger.debug(f"Não foi possível processar como WAV: {e}, tentando como PCM raw")
            buffer.seek(0)  # Reiniciar o buffer
        
        # Reproduzir como PCM raw
        chunk_size = self.chunk_size * self.channels * self.pa.get_sample_size(self.format)
        
        while True:
            data = buffer.read(chunk_size)
            if not data:
                break
                
            self.stream.write(data)
            await asyncio.sleep(0)  # Yield para o event loop
        
        logger.debug("Reprodução de áudio concluída")
    
    async def _play_file(self, file_path: str) -> None:
        """
        Reproduz áudio a partir de um arquivo.
        
        Args:
            file_path: Caminho para o arquivo de áudio
        
        Raises:
            FileNotFoundError: Se o arquivo não existir
        """
        try:
            with wave.open(file_path, "rb") as wf:
                # Obter parâmetros do arquivo WAV
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                framerate = wf.getframerate()
                
                # Reconfigurar o stream se necessário
                if channels != self.channels or framerate != self.sample_rate:
                    self._close_stream()
                    self.channels = channels
                    self.sample_rate = framerate
                    self._open_stream()
                
                logger.debug(f"Reproduzindo arquivo {file_path}")
                
                # Leitura e reprodução dos dados
                data = wf.readframes(self.chunk_size)
                while len(data) > 0:
                    self.stream.write(data)
                    data = wf.readframes(self.chunk_size)
                    await asyncio.sleep(0)  # Yield para o event loop
                
                logger.debug("Reprodução do arquivo concluída")
        except FileNotFoundError:
            logger.error(f"Arquivo não encontrado: {file_path}")
            raise FileNotFoundError(f"Arquivo de áudio não encontrado: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao reproduzir arquivo {file_path}: {e}")
            raise RuntimeError(f"Falha ao reproduzir arquivo de áudio: {e}")
    
    def close(self) -> None:
        """Fecha o reprodutor de áudio e libera recursos."""
        self._close_stream()
        if self.pa:
            self.pa.terminate()
            logger.debug("PyAudio encerrado")
