"""
Módulo para reprodução de áudio através dos alto-falantes.

Este módulo implementa a funcionalidade de reprodução de áudio usando sounddevice
com foco em simplicidade e estabilidade.
"""

import asyncio
import io
import numpy as np
import sounddevice as sd
import soundfile as sf
import wave
import tempfile
import os
from typing import Any, Dict, Optional, Union

from src.utils.logger import get_logger

logger = get_logger(__name__)

class AudioPlayer:
    """
    Classe para reprodução de áudio através dos alto-falantes.
    
    Implementa a funcionalidade de reprodução de áudio usando sounddevice,
    com foco em estabilidade e qualidade.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o reprodutor de áudio com as configurações especificadas.
        
        Args:
            config: Dicionário com configurações de áudio
        """
        self.config = config
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("output_channels", config.get("channels", 2))
        
        # Diretório temporário para arquivos de áudio
        self.temp_dir = tempfile.mkdtemp(prefix="turrão_audio_")
        
        # Contador para nomes de arquivos únicos
        self.file_counter = 0
        
        # Flag para indicar se estamos reproduzindo áudio
        self.is_playing = False
        
        # Configurar o dispositivo padrão
        try:
            devices = sd.query_devices()
            default_output = sd.default.device[1]
            device_info = sd.query_devices(default_output)
            
            logger.info(f"Dispositivo de saída: {device_info['name']}")
            logger.info(f"Taxa de amostragem suportada: {device_info['default_samplerate']}")
            logger.info(f"Canais de saída: {device_info['max_output_channels']}")
            
            # Ajustar canais se necessário
            if self.channels > device_info['max_output_channels']:
                logger.warning(f"Ajustando canais para {device_info['max_output_channels']} (máximo suportado)")
                self.channels = device_info['max_output_channels']
            
            logger.debug("AudioPlayer inicializado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao verificar dispositivos de áudio: {e}")
    
    async def write(self, audio_data: bytes) -> None:
        """
        Método para compatibilidade com a interface do RealtimeAgent.
        Processa e reproduz o áudio recebido.
        
        Args:
            audio_data: Dados de áudio em bytes
        """
        try:
            # Gerar um arquivo temporário para o áudio
            temp_file = os.path.join(self.temp_dir, f"audio_{self.file_counter}.wav")
            self.file_counter += 1
            
            # Salvar os bytes como arquivo WAV
            self._save_wav(audio_data, temp_file)
            
            # Reproduzir o arquivo
            await self._play_file(temp_file)
            
            # Remover o arquivo temporário após reprodução
            try:
                os.remove(temp_file)
            except:
                pass  # Ignorar erros na remoção
                
        except Exception as e:
            logger.error(f"Erro ao processar áudio: {e}")
    
    def _save_wav(self, audio_bytes: bytes, file_path: str) -> None:
        """
        Salva os bytes de áudio como um arquivo WAV.
        
        Args:
            audio_bytes: Dados de áudio em bytes
            file_path: Caminho para salvar o arquivo WAV
        """
        try:
            # Converter para array numpy (assumindo PCM16, que é o formato padrão da OpenAI)
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Se precisarmos de estéreo e temos mono
            if self.channels > 1 and len(audio_data.shape) == 1:
                # Duplicar o canal para estéreo
                audio_data = np.column_stack([audio_data] * self.channels)
            
            # Salvar como WAV usando soundfile
            sf.write(file_path, audio_data, self.sample_rate)
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo WAV: {e}")
            raise
    
    async def play(self, audio_data: Union[bytes, str]) -> None:
        """
        Reproduz dados de áudio ou um arquivo de áudio.
        
        Args:
            audio_data: Dados de áudio como bytes ou caminho para um arquivo de áudio
        """
        try:
            # Verificar se audio_data é um caminho para arquivo
            if isinstance(audio_data, str):
                await self._play_file(audio_data)
            else:
                # Para bytes, usamos o método write
                await self.write(audio_data)
        except Exception as e:
            logger.error(f"Erro durante a reprodução de áudio: {e}")
    
    async def _play_file(self, file_path: str) -> None:
        """
        Reproduz áudio a partir de um arquivo usando método mais direto.
        
        Args:
            file_path: Caminho para o arquivo de áudio
        """
        try:
            # Usar um player externo em vez de sounddevice, mais confiável em alguns sistemas
            # Para Windows, usamos o comando 'start' que é não-bloqueante
            import platform
            if platform.system() == 'Windows':
                cmd = f'start /min "" "{file_path}"'
                os.system(cmd)
                await asyncio.sleep(0.1)  # Pequena pausa não-bloqueante
            else:
                # Alternativa para não-Windows: usar sounddevice
                data, sample_rate = sf.read(file_path)
                sd.play(data, sample_rate)
                await asyncio.sleep(0.1)  # Pequena pausa não-bloqueante
            
            logger.debug(f"Reprodução do arquivo {file_path} iniciada")
        except Exception as e:
            logger.error(f"Erro ao reproduzir arquivo {file_path}: {e}")
    
    def close(self) -> None:
        """Fecha o reprodutor de áudio e libera recursos."""
        try:
            # Parar qualquer reprodução em andamento
            sd.stop()
            
            # Limpar arquivos temporários
            for file in os.listdir(self.temp_dir):
                try:
                    os.remove(os.path.join(self.temp_dir, file))
                except:
                    pass
            
            try:
                os.rmdir(self.temp_dir)
            except:
                pass
                
            logger.debug("Recursos de áudio liberados")
        except Exception as e:
            logger.error(f"Erro ao liberar recursos de áudio: {e}")
