"""
Módulo para captura de áudio através do microfone.

Este módulo implementa a funcionalidade de gravação de áudio do microfone
usando sounddevice e outras bibliotecas de áudio modernas e compatíveis.
"""

import asyncio
import io
from typing import Any, Dict, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioRecorder:
    """
    Classe para gravação de áudio do microfone.
    
    Implementa a funcionalidade de captura de áudio usando sounddevice,
    com suporte para detecção de silêncio e gravação contínua ou por comando.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o gravador de áudio com as configurações especificadas.
        
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
        
        # Configuração para detecção de silêncio
        self.silence_threshold = config.get("silence_threshold", 700)  # Valor padrão para formato Int16
        self.silence_duration = config.get("silence_duration", 1.0)  # Segundos
        
        # Verificar dispositivos disponíveis
        try:
            self.devices = sd.query_devices()
            input_device = sd.default.device[0]
            logger.debug(f"Dispositivo de entrada padrão: {input_device}")
            logger.debug("AudioRecorder inicializado com sucesso")
        except Exception as e:
            logger.critical(f"Erro ao inicializar dispositivo de áudio: {e}")
            raise RuntimeError(f"Falha na inicialização do dispositivo de áudio: {e}")
    
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
            # Aviso de início da gravação
            logger.info("Gravando... (fale agora)")
            
            # Coletar dados de áudio
            max_duration = duration or 60  # Limite de 60s se duração não especificada
            
            # Lista para armazenar os frames de áudio
            audio_frames = []
            silence_frames = 0
            silence_limit = int(self.silence_duration * self.sample_rate / self.chunk_size)
            
            # Callback para processamento do áudio
            def callback(indata, frames, time, status):
                nonlocal silence_frames
                
                if status:
                    logger.warning(f"Status de áudio: {status}")
                
                # Converter para o formato adequado
                audio_chunk = indata.copy()
                
                # Verificar nível de áudio
                if not self._is_above_threshold(audio_chunk):
                    silence_frames += 1
                else:
                    silence_frames = 0
                
                audio_frames.append(audio_chunk)
            
            # Configurar o stream com callback
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.chunk_size,
                callback=callback
            )
            
            # Iniciar gravação
            with stream:
                # Remover ruído inicial (500ms)
                await asyncio.sleep(0.5)
                
                # Esperar por algum som que não seja silêncio
                is_speaking = False
                timeout = 10  # 10 segundos de espera
                start_time = asyncio.get_event_loop().time()
                
                while not is_speaking and (asyncio.get_event_loop().time() - start_time) < timeout:
                    if len(audio_frames) > 0 and self._is_above_threshold(audio_frames[-1]):
                        is_speaking = True
                        break
                    await asyncio.sleep(0.1)
                
                if not is_speaking:
                    logger.info("Nenhum áudio detectado, encerrando gravação")
                    return b""
                
                # Continuar gravando até detectar silêncio prolongado ou atingir duração máxima
                recording_start = asyncio.get_event_loop().time()
                
                while True:
                    current_time = asyncio.get_event_loop().time()
                    elapsed = current_time - recording_start
                    
                    # Verificar duração máxima
                    if elapsed >= max_duration:
                        logger.info("Atingida duração máxima de gravação")
                        break
                    
                    # Verificar silêncio
                    if silence_frames >= silence_limit:
                        logger.info("Silêncio detectado, encerrando gravação")
                        break
                    
                    await asyncio.sleep(0.1)
            
            # Combinar todos os frames em um único buffer de áudio
            if not audio_frames:
                return b""
                
            combined_audio = np.vstack(audio_frames)
            
            # Converter para bytes
            byte_io = io.BytesIO()
            sf.write(byte_io, combined_audio, self.sample_rate, format='WAV')
            byte_io.seek(0)
            audio_data = byte_io.read()
            
            logger.info("Gravação concluída")
            return audio_data
            
        except Exception as e:
            logger.error(f"Erro durante a gravação: {e}")
            raise RuntimeError(f"Falha na gravação de áudio: {e}")
    
    def _is_above_threshold(self, data: np.ndarray) -> bool:
        """
        Verifica se o nível de áudio está acima do limiar de silêncio.
        
        Args:
            data: Dados de áudio a serem verificados
        
        Returns:
            True se o áudio estiver acima do limiar de silêncio
        """
        # Calcular o valor RMS (root mean square)
        rms = np.sqrt(np.mean(np.square(data)))
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
            # Abrir os dados como um arquivo WAV
            with io.BytesIO(audio_data) as buf:
                data, sample_rate = sf.read(buf)
                sf.write(filename, data, sample_rate)
            
            logger.debug(f"Áudio salvo em {filename}")
        except Exception as e:
            logger.error(f"Erro ao salvar áudio em {filename}: {e}")
            raise IOError(f"Falha ao salvar arquivo de áudio: {e}")
    
    def close(self) -> None:
        """Fecha o gravador de áudio e libera recursos."""
        # Não é necessário fechar o sounddevice explicitamente, 
        # mas mantemos o método para compatibilidade
        logger.debug("Recursos de áudio liberados")
