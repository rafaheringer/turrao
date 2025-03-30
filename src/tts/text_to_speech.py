"""
Implementação do módulo de Text-to-Speech (TTS) para o assistente Turrão.

Este módulo é responsável por converter texto em áudio usando diversos
mecanismos de síntese de voz, tanto online quanto offline.
"""

import asyncio
import io
import os
import tempfile
from typing import Any, Dict, Optional

# Importação condicional para gTTS
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

# Importação condicional para pyttsx3
try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TextToSpeech:
    """
    Classe para conversão de texto para fala (TTS).
    
    Implementa a conversão de texto para fala usando diferentes engines,
    como gTTS (Google Text-to-Speech, online) e pyttsx3 (offline).
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o conversor de texto para fala com as configurações especificadas.
        
        Args:
            config: Dicionário com configurações para TTS
            
        Raises:
            ImportError: Se nenhum engine TTS estiver disponível
        """
        self.config = config
        self.provider = config.get("provider", "auto").lower()
        self.voice = config.get("voice", "pt-BR")
        self.rate = config.get("rate", 1.0)
        
        # Verificar engines disponíveis
        self.has_gtts = HAS_GTTS
        self.has_pyttsx3 = HAS_PYTTSX3
        
        if not self.has_gtts and not self.has_pyttsx3:
            logger.critical("Nenhum engine TTS disponível. Instale gTTS ou pyttsx3.")
            raise ImportError("Pelo menos um engine TTS (gTTS ou pyttsx3) é necessário")
        
        # Inicializar engine offline se disponível
        self.pyttsx3_engine = None
        if self.has_pyttsx3 and (self.provider == "pyttsx3" or self.provider == "auto"):
            try:
                self.pyttsx3_engine = pyttsx3.init()
                
                # Configurar voz
                voices = self.pyttsx3_engine.getProperty('voices')
                for voice in voices:
                    if self.voice.lower() in voice.id.lower():
                        self.pyttsx3_engine.setProperty('voice', voice.id)
                        break
                
                # Configurar taxa de fala
                self.pyttsx3_engine.setProperty('rate', 
                                              self.pyttsx3_engine.getProperty('rate') * self.rate)
                
                logger.debug("Engine pyttsx3 inicializado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao inicializar pyttsx3: {e}")
                self.has_pyttsx3 = False
                self.pyttsx3_engine = None
        
        # Determinar qual provider usar com base na disponibilidade
        if self.provider == "auto":
            if self.has_gtts:
                self.active_provider = "gtts"
            elif self.has_pyttsx3:
                self.active_provider = "pyttsx3"
        else:
            if self.provider == "gtts" and not self.has_gtts:
                logger.warning("gTTS solicitado mas não disponível, tentando alternativa")
                if self.has_pyttsx3:
                    self.active_provider = "pyttsx3"
                else:
                    raise ImportError("gTTS solicitado mas não está instalado")
            elif self.provider == "pyttsx3" and not self.has_pyttsx3:
                logger.warning("pyttsx3 solicitado mas não disponível, tentando alternativa")
                if self.has_gtts:
                    self.active_provider = "gtts"
                else:
                    raise ImportError("pyttsx3 solicitado mas não está instalado")
            else:
                self.active_provider = self.provider
        
        logger.info(f"TTS inicializado com provider: {self.active_provider}")
    
    async def synthesize(self, text: str) -> bytes:
        """
        Converte texto em áudio.
        
        Args:
            text: Texto a ser convertido em áudio
            
        Returns:
            Dados de áudio em bytes
            
        Raises:
            RuntimeError: Se ocorrer erro durante a síntese
        """
        if not text:
            logger.warning("Texto vazio fornecido para síntese")
            return b""
        
        try:
            # Executar a síntese em uma thread separada para não bloquear o event loop
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(
                None, 
                lambda: self._synthesize_text(text)
            )
            
            logger.debug(f"Síntese de voz concluída para: '{text[:50]}...' se mais longo")
            return audio_data
            
        except Exception as e:
            logger.error(f"Erro durante a síntese de voz: {e}")
            raise RuntimeError(f"Falha na síntese de voz: {e}")
    
    def _synthesize_text(self, text: str) -> bytes:
        """
        Realiza a síntese de voz usando o engine configurado.
        
        Args:
            text: Texto a ser convertido em áudio
            
        Returns:
            Dados de áudio em bytes
            
        Raises:
            RuntimeError: Se ocorrer erro durante a síntese
        """
        if self.active_provider == "gtts":
            return self._synthesize_gtts(text)
        elif self.active_provider == "pyttsx3":
            return self._synthesize_pyttsx3(text)
        else:
            logger.error(f"Provider TTS desconhecido: {self.active_provider}")
            raise RuntimeError(f"Provider TTS não suportado: {self.active_provider}")
    
    def _synthesize_gtts(self, text: str) -> bytes:
        """
        Sintetiza voz usando Google Text-to-Speech (gTTS).
        
        Args:
            text: Texto a ser convertido
            
        Returns:
            Dados de áudio em bytes
        """
        # Ajustar idioma para formato compatível com gTTS
        lang = self.voice.split('-')[0]  # Extrair o código do idioma (pt-BR -> pt)
        
        # Criar objeto gTTS
        tts = gTTS(text=text, lang=lang, slow=False)
        
        # Salvar para um buffer temporário
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        
        # Ler o conteúdo do buffer
        return mp3_fp.read()
    
    def _synthesize_pyttsx3(self, text: str) -> bytes:
        """
        Sintetiza voz usando pyttsx3 (offline TTS).
        
        Args:
            text: Texto a ser convertido
            
        Returns:
            Dados de áudio em bytes
        """
        if not self.pyttsx3_engine:
            raise RuntimeError("Engine pyttsx3 não está inicializado")
        
        # pyttsx3 não pode salvar diretamente para um buffer em memória,
        # então usamos um arquivo temporário
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_filename = temp_file.name
        
        try:
            # Sintetizar para o arquivo temporário
            self.pyttsx3_engine.save_to_file(text, temp_filename)
            self.pyttsx3_engine.runAndWait()
            
            # Ler o arquivo temporário
            with open(temp_filename, 'rb') as f:
                audio_data = f.read()
            
            return audio_data
            
        finally:
            # Limpar o arquivo temporário
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
