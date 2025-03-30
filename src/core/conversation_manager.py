"""
Gerenciador de conversação para o assistente Turrão.

Este módulo implementa a lógica de gerenciamento de conversação,
mantendo o histórico, aplicando a personalidade e coordenando a interação
com a API Realtime da OpenAI.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
import queue
import threading

import sounddevice as sd
import numpy as np

from src.api.realtime_agent import RealtimeAgent
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """
    Gerenciador de conversação do assistente Turrão.
    
    Responsável por manter o contexto da conversa, gerenciar o histórico
    e aplicar a personalidade do assistente nas interações utilizando
    a API Realtime da OpenAI.
    """
    
    def __init__(self, realtime_agent: RealtimeAgent, config: Dict[str, Any]):
        """
        Inicializa o gerenciador de conversação.
        
        Args:
            realtime_agent: Agente Realtime para comunicação com a API da OpenAI
            config: Configurações do assistente
        """
        self.realtime_agent = realtime_agent
        self.config = config
        
        # Configurações de personalidade
        self.assistant_name = config.get("name", "Turrão")
        self.personality = config.get("personality", "")
        self.max_history = config.get("max_history", 10)
        
        # Histórico de conversação (mantido para compatibilidade e possível uso futuro)
        self.conversation_history: List[Dict[str, str]] = []
        
        # Sessão atual
        self.session_start_time = datetime.now()
        self.session_id = f"session_{self.session_start_time.strftime('%Y%m%d_%H%M%S')}"
        
        # Configurações de áudio
        self.audio_config = {
            "sample_rate": 16000,  # A API Realtime funciona bem com 16kHz
            "channels": 1,         # Mono para a entrada de voz
            "dtype": "float32",    # Formato padrão para áudio
            "blocksize": 1024,     # Tamanho do bloco para streaming
            "latency": "low"       # Baixa latência para conversação natural
        }
        
        # Filas para streaming de áudio
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
        # Flag para controle de streaming
        self.streaming = False
        
        # Configurar a personalidade no agente Realtime
        personality_prompt = self._create_system_prompt()
        self.realtime_agent.set_personality(personality_prompt)
        
        logger.info(f"Gerenciador de conversação inicializado para o assistente {self.assistant_name}")
    
    def _create_system_prompt(self) -> str:
        """
        Cria o prompt de sistema que define a personalidade do assistente.
        
        Returns:
            Prompt de sistema formatado
        """
        # Prompt base com a personalidade do Turrão
        if self.personality:
            system_prompt = self.personality
        else:
            system_prompt = (
                "Você é o Turrão, um assistente pessoal com personalidade forte, irreverente e humor ácido. "
                "Você é teimoso, direto e não tem papas na língua. "
                "Você responde com sarcasmo e ironia, mantendo um tom assertivo mas sempre com humor picante. "
                "Você não é rude, apenas sincero e bem-humorado, usando expressões típicas brasileiras."
            )
        
        # Adicionar informações de contexto
        system_prompt += f"\n\nHoje é {datetime.now().strftime('%d/%m/%Y')} e são aproximadamente {datetime.now().strftime('%H:%M')}."
        
        # Adicionar regras específicas
        system_prompt += """
        
        Regras de comportamento:
        1. Mantenha seu tom teimoso, irreverente e com humor ácido em todas as respostas
        2. Seja direto e objetivo, mas nunca perca a oportunidade de inserir uma piada ou comentário sarcástico
        3. Quando não souber uma resposta, admita com sinceridade, mas mantenha seu estilo único
        4. Evite respostas genéricas que poderiam vir de qualquer assistente
        5. Use gírias brasileiras ocasionalmente para dar mais personalidade às respostas
        6. Tenha opiniões próprias e defenda-as com veemência, mesmo que precise modificá-las frente a novos fatos
        7. Seja implicante de forma bem-humorada, como um amigo próximo seria
        8. Varie suas respostas e expressões para manter o diálogo interessante
        """
        
        return system_prompt

    def _audio_input_callback(self, indata, frames, time, status):
        """
        Callback para captura de áudio do microfone.
        
        Este callback é chamado pela biblioteca sounddevice para cada bloco de áudio capturado.
        Os dados são colocados na fila de entrada para processamento pela API Realtime.
        
        Args:
            indata: Array NumPy contendo os dados de áudio capturados
            frames: Número de frames no bloco
            time: Informações de timestamp
            status: Status da captura, incluindo possíveis erros
        """
        if status:
            logger.warning(f"Status de entrada de áudio: {status}")
        
        if self.streaming:
            # Converter para o formato correto se necessário
            audio_chunk = indata.copy()
            self.input_queue.put(audio_chunk)

    def _audio_output_callback(self, outdata, frames, time, status):
        """
        Callback para reprodução de áudio nos alto-falantes.
        
        Este callback é chamado pela biblioteca sounddevice quando precisa de dados para reprodução.
        Os dados são obtidos da fila de saída onde a API Realtime coloca o áudio gerado.
        
        Args:
            outdata: Array NumPy onde os dados de áudio para reprodução devem ser colocados
            frames: Número de frames solicitados
            time: Informações de timestamp
            status: Status da reprodução, incluindo possíveis erros
        """
        if status:
            logger.warning(f"Status de saída de áudio: {status}")
        
        try:
            if not self.streaming:
                outdata.fill(0)  # Silêncio quando não estiver em streaming
                return
                
            # Tentar obter dados da fila de saída
            data = self.output_queue.get_nowait()
            if len(data) < len(outdata):
                outdata[:len(data)] = data
                outdata[len(data):].fill(0)
            else:
                outdata[:] = data[:len(outdata)]
        except queue.Empty:
            outdata.fill(0)  # Silêncio se não houver dados disponíveis

    class AudioInputStream:
        """Stream de entrada de áudio para a API Realtime."""
        
        def __init__(self, queue_obj):
            self.queue = queue_obj
            
        async def read(self, size):
            """
            Lê dados de áudio da fila de entrada.
            
            Args:
                size: Tamanho dos dados a serem lidos
                
            Returns:
                Dados de áudio ou None se não houver dados disponíveis
            """
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.queue.get(block=True, timeout=0.5)
                )
                return data.tobytes()
            except (queue.Empty, asyncio.CancelledError):
                return None
                
    class AudioOutputStream:
        """Stream de saída de áudio para a API Realtime."""
        
        def __init__(self, queue_obj):
            self.queue = queue_obj
            
        async def write(self, chunk):
            """
            Escreve dados de áudio na fila de saída.
            
            Args:
                chunk: Dados de áudio a serem reproduzidos
            """
            if chunk:
                # Converter bytes para numpy array
                audio_array = np.frombuffer(chunk, dtype=np.float32)
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.queue.put(audio_array)
                )
    
    async def start_realtime_conversation(self, 
                                         on_speech_recognized: Optional[Callable[[str], None]] = None,
                                         on_response_started: Optional[Callable[[], None]] = None,
                                         on_response_text: Optional[Callable[[str], None]] = None,
                                         on_completion: Optional[Callable[[], None]] = None):
        """
        Inicia uma conversação em tempo real usando a API Realtime.
        
        Args:
            on_speech_recognized: Callback para quando a fala é reconhecida
            on_response_started: Callback para quando a resposta começa
            on_response_text: Callback para cada trecho de texto da resposta
            on_completion: Callback para quando a conversação é concluída
        """
        try:
            logger.info("Iniciando conversação em tempo real")
            
            # Preparar streams de áudio
            audio_input_stream = self.AudioInputStream(self.input_queue)
            audio_output_stream = self.AudioOutputStream(self.output_queue)
            
            # Iniciar streaming de áudio
            self.streaming = True
            
            # Iniciar streams de captura e reprodução
            input_stream = sd.InputStream(
                samplerate=self.audio_config["sample_rate"],
                channels=self.audio_config["channels"],
                dtype=self.audio_config["dtype"],
                blocksize=self.audio_config["blocksize"],
                latency=self.audio_config["latency"],
                callback=self._audio_input_callback
            )
            
            output_stream = sd.OutputStream(
                samplerate=self.audio_config["sample_rate"],
                channels=self.audio_config["channels"],
                dtype=self.audio_config["dtype"],
                blocksize=self.audio_config["blocksize"],
                latency=self.audio_config["latency"],
                callback=self._audio_output_callback
            )
            
            # Iniciar as streams
            input_stream.start()
            output_stream.start()
            
            logger.info("Streams de áudio iniciadas")
            
            try:
                # Iniciar a sessão de conversação em tempo real
                await self.realtime_agent.start_conversation(
                    audio_input_stream=audio_input_stream,
                    audio_output_stream=audio_output_stream,
                    on_speech_recognized=on_speech_recognized,
                    on_response_started=on_response_started,
                    on_response_text=on_response_text,
                    on_completion=on_completion
                )
            finally:
                # Garantir que os streams sejam fechados mesmo em caso de erro
                self.streaming = False
                input_stream.stop()
                output_stream.stop()
                input_stream.close()
                output_stream.close()
                logger.info("Streams de áudio encerradas")
            
            logger.info("Conversação em tempo real concluída")
            
        except Exception as e:
            logger.error(f"Erro na conversação em tempo real: {e}")
            raise RuntimeError(f"Falha na conversação em tempo real: {e}")
    
    def clear_history(self) -> None:
        """Limpa o histórico de conversação atual."""
        self.conversation_history = []
        logger.debug("Histórico de conversação foi limpo")
    
    async def save_conversation(self, file_path: Optional[str] = None) -> str:
        """
        Salva a conversa atual em um arquivo JSON.
        
        Args:
            file_path: Caminho opcional para salvar o arquivo
            
        Returns:
            Caminho do arquivo salvo
        """
        # Se não for fornecido um caminho, criar um com base na sessão atual
        if not file_path:
            os.makedirs("conversations", exist_ok=True)
            file_path = f"conversations/{self.session_id}.json"
        
        # Preparar os dados para salvar
        conversation_data = {
            "session_id": self.session_id,
            "start_time": self.session_start_time.isoformat(),
            "assistant_name": self.assistant_name,
            "history": self.conversation_history
        }
        
        # Salvar o arquivo
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Conversação salva em {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Erro ao salvar conversa: {e}")
            raise IOError(f"Falha ao salvar arquivo de conversação: {e}")
    
    async def load_conversation(self, file_path: str) -> None:
        """
        Carrega uma conversa de um arquivo JSON.
        
        Args:
            file_path: Caminho do arquivo a ser carregado
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                conversation_data = json.load(f)
            
            # Extrair os dados
            self.session_id = conversation_data.get("session_id", self.session_id)
            self.conversation_history = conversation_data.get("history", [])
            
            logger.info(f"Conversação carregada de {file_path}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar conversa: {e}")
            raise IOError(f"Falha ao carregar arquivo de conversação: {e}")
