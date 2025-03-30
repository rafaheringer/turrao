"""
Implementação do módulo de Speech-to-Text (STT) para o assistente Turrão.

Este módulo é responsável por converter áudio em texto usando reconhecimento de fala.
"""

import asyncio
import io
import os
from typing import Any, Dict, Optional

# Importação condicional para SpeechRecognition
try:
    import speech_recognition as sr
    HAS_SPEECH_RECOGNITION = True
except ImportError:
    HAS_SPEECH_RECOGNITION = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SpeechToText:
    """
    Classe para conversão de fala para texto usando diversas APIs e engines.
    
    Implementa funcionalidades de reconhecimento de fala usando bibliotecas como
    SpeechRecognition, que dá acesso a múltiplos providers como Google, Whisper, etc.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o conversor de fala para texto com as configurações especificadas.
        
        Args:
            config: Dicionário com configurações para STT
            
        Raises:
            ImportError: Se as dependências necessárias não estiverem instaladas
        """
        if not HAS_SPEECH_RECOGNITION:
            logger.critical("SpeechRecognition não está instalado. A conversão de fala para texto não funcionará.")
            raise ImportError("SpeechRecognition é necessário para o reconhecimento de fala")
        
        self.config = config
        self.recognizer = sr.Recognizer()
        
        # Configurações do reconhecedor
        self.language = config.get("language", "pt-BR")
        self.model = config.get("model", "default")
        
        # Ajustes para adaptação ao ambiente
        self.energy_threshold = config.get("energy_threshold", 300)
        self.recognizer.energy_threshold = self.energy_threshold
        
        # Configuração de timeout
        self.timeout = config.get("timeout", 5)
        self.phrase_time_limit = config.get("phrase_time_limit", 10)
        
        logger.debug(f"SpeechToText inicializado com idioma '{self.language}' e modelo '{self.model}'")
    
    async def transcribe(self, audio_data: bytes) -> str:
        """
        Converte dados de áudio em texto.
        
        Args:
            audio_data: Dados de áudio em bytes para converter
            
        Returns:
            Texto reconhecido a partir do áudio
            
        Raises:
            RuntimeError: Se ocorrer erro durante o reconhecimento
        """
        if not audio_data:
            logger.warning("Dados de áudio vazios fornecidos para transcrição")
            return ""
        
        try:
            # Converter bytes em um objeto AudioData que o SpeechRecognition entende
            audio_io = io.BytesIO(audio_data)
            
            # Executar o reconhecimento em uma thread separada para não bloquear o event loop
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None, self._perform_recognition, audio_io
            )
            
            logger.info(f"Transcrição concluída: '{text}'")
            return text
            
        except Exception as e:
            logger.error(f"Erro durante o reconhecimento de fala: {e}")
            # Retornar string vazia em caso de erro, para que o assistente possa continuar
            return ""
    
    def _perform_recognition(self, audio_io: io.BytesIO) -> str:
        """
        Realiza o reconhecimento de fala usando o engine configurado.
        
        Args:
            audio_io: Buffer de áudio para reconhecimento
            
        Returns:
            Texto reconhecido
            
        Raises:
            RuntimeError: Se ocorrer erro durante o reconhecimento
        """
        try:
            # Criar objeto AudioData a partir do buffer
            with sr.AudioFile(audio_io) as source:
                audio = self.recognizer.record(source)
            
            # Selecionar o engine de reconhecimento com base na configuração
            if self.model == "google":
                text = self.recognizer.recognize_google(
                    audio, 
                    language=self.language
                )
            elif self.model == "whisper":
                # Verificar se temos uma API key do Whisper
                api_key = os.environ.get("OPENAI_API_KEY", self.config.get("api_key"))
                if not api_key:
                    logger.warning("API key do OpenAI não configurada para Whisper, usando modo offline")
                    # Usar Whisper em modo offline
                    text = self.recognizer.recognize_whisper(
                        audio, 
                        language=self.language.split("-")[0]  # Whisper usa formato de idioma diferente (pt em vez de pt-BR)
                    )
                else:
                    # Usar Whisper através da API do OpenAI
                    text = self.recognizer.recognize_whisper_api(
                        audio,
                        api_key=api_key,
                        language=self.language.split("-")[0]
                    )
            elif self.model == "sphinx":
                # CMU Sphinx - reconhecimento offline
                text = self.recognizer.recognize_sphinx(audio, language=self.language)
            else:
                # Modelo padrão - usar o que estiver disponível
                # Tentar Whisper primeiro, depois Google, depois Sphinx como fallback
                try:
                    text = self.recognizer.recognize_whisper(
                        audio, 
                        language=self.language.split("-")[0]
                    )
                except:
                    try:
                        text = self.recognizer.recognize_google(audio, language=self.language)
                    except:
                        text = self.recognizer.recognize_sphinx(audio, language=self.language)
            
            return text
            
        except sr.UnknownValueError:
            logger.warning("Fala não reconhecida")
            return ""
        except sr.RequestError as e:
            logger.error(f"Erro na requisição ao serviço de reconhecimento: {e}")
            return ""
        except Exception as e:
            logger.error(f"Erro inesperado durante o reconhecimento: {e}")
            return ""
