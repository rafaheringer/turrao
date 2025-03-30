"""
Módulo para reprodução de áudio através dos alto-falantes.

Este módulo implementa a funcionalidade de reprodução de áudio usando sounddevice
e outras bibliotecas de áudio modernas e compatíveis com Python 3.12.
"""

import asyncio
import io
from typing import Any, Dict, Optional, Union

import numpy as np
import sounddevice as sd
import soundfile as sf

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioPlayer:
    """
    Classe para reprodução de áudio através dos alto-falantes.
    
    Implementa a funcionalidade de reprodução de áudio usando sounddevice,
    suportando diferentes formatos e taxas de amostragem.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o reprodutor de áudio com as configurações especificadas.
        
        Args:
            config: Dicionário com configurações de áudio
        
        Raises:
            RuntimeError: Se ocorrer erro na inicialização do dispositivo de áudio
        """
        self.config = config
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.chunk_size = config.get("chunk_size", 1024)
        
        # Mapeamento de formatos de áudio para numpy
        format_map = {
            "Int8": np.int8,
            "Int16": np.int16,
            "Int32": np.int32,
            "Float32": np.float32
        }
        format_str = config.get("format", "Int16")
        self.dtype = format_map.get(format_str, np.int16)
        
        # Verificar dispositivos disponíveis
        try:
            self.devices = sd.query_devices()
            output_device = sd.default.device[1]
            logger.debug(f"Dispositivo de saída padrão: {output_device}")
            logger.debug("AudioPlayer inicializado com sucesso")
        except Exception as e:
            logger.critical(f"Erro ao inicializar dispositivo de áudio: {e}")
            raise RuntimeError(f"Falha na inicialização do dispositivo de áudio: {e}")
    
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
        try:
            # Criar buffer de memória com os dados
            buffer = io.BytesIO(audio_data)
            
            # Carregar os dados usando soundfile
            data, samplerate = sf.read(buffer)
            
            # Reprodução usando sounddevice
            # Usamos blocksize=0 para reprodução não-bloqueante e sem callback
            await self._play_data(data, samplerate)
            
            logger.debug("Reprodução de áudio concluída")
        except Exception as e:
            logger.error(f"Erro na reprodução de áudio de bytes: {e}")
            raise RuntimeError(f"Falha na reprodução de áudio: {e}")
    
    async def _play_file(self, file_path: str) -> None:
        """
        Reproduz áudio a partir de um arquivo.
        
        Args:
            file_path: Caminho para o arquivo de áudio
        
        Raises:
            FileNotFoundError: Se o arquivo não existir
        """
        try:
            # Carregar o arquivo de áudio
            data, samplerate = sf.read(file_path)
            
            logger.debug(f"Reproduzindo arquivo {file_path}")
            
            # Reproduzir os dados
            await self._play_data(data, samplerate)
            
            logger.debug("Reprodução do arquivo concluída")
        except FileNotFoundError:
            logger.error(f"Arquivo não encontrado: {file_path}")
            raise FileNotFoundError(f"Arquivo de áudio não encontrado: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao reproduzir arquivo {file_path}: {e}")
            raise RuntimeError(f"Falha ao reproduzir arquivo de áudio: {e}")
    
    async def _play_data(self, data: np.ndarray, samplerate: int) -> None:
        """
        Reproduz dados de áudio já carregados na memória.
        
        Args:
            data: Array com os dados de áudio
            samplerate: Taxa de amostragem dos dados
        """
        # Criar um evento para sinalizar quando a reprodução termina
        finished = asyncio.Event()
        
        def callback(outdata, frames, time, status):
            if status:
                logger.warning(f"Status de áudio: {status}")
        
        # Reproduzir os dados
        with sd.OutputStream(
            samplerate=samplerate,
            channels=data.shape[1] if len(data.shape) > 1 else 1,
            callback=callback
        ) as stream:
            sd.play(data, samplerate=samplerate, blocking=False)
            
            # Verificar o status de reprodução periodicamente
            while sd.get_stream().active:
                await asyncio.sleep(0.1)  # Verificar a cada 100ms
    
    def close(self) -> None:
        """Fecha o reprodutor de áudio e libera recursos."""
        # Não é necessário fechar o sounddevice explicitamente, 
        # mas mantemos o método para compatibilidade
        logger.debug("Recursos de áudio liberados")
