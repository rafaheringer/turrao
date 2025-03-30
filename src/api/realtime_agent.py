"""
Cliente para comunicação com a API Realtime do OpenAI para agentes de voz.

Este módulo implementa a interação com a API Realtime da OpenAI,
permitindo conversação bidirecional de voz em tempo real.
"""

import asyncio
import json
import os
import time
import traceback
import base64
import logging
from typing import Any, Callable, Dict, List, Optional, Union

import openai
from openai import AsyncOpenAI

from src.utils.logger import get_logger

# Forçar o nível de log para DEBUG
logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)


class RealtimeAgent:
    """
    Agente de voz em tempo real usando a API Realtime da OpenAI.
    
    Implementa funcionalidades para comunicação bidirecional de voz
    em tempo real, eliminando a necessidade de módulos STT e TTS separados.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o agente de voz em tempo real com as configurações especificadas.
        
        Args:
            config: Dicionário com configurações para a API
            
        Raises:
            ImportError: Se o SDK do OpenAI não estiver na versão adequada
            ValueError: Se a chave de API não estiver configurada
        """
        # Verificar versão do OpenAI SDK (a API Realtime exige a versão recente)
        try:
            # Tentar criar uma instância do cliente com beta.realtime
            client = AsyncOpenAI()
            # Verificar se o atributo beta.realtime existe
            if not hasattr(client, 'beta') or not hasattr(client.beta, 'realtime'):
                logger.critical("SDK do OpenAI não possui suporte para API Realtime (beta.realtime)")
                raise ImportError("SDK do OpenAI precisa ser da versão que suporta a API Realtime")
        except Exception as e:
            logger.critical(f"Erro ao verificar suporte para API Realtime: {e}")
            raise ImportError(f"Erro ao inicializar cliente com suporte à API Realtime: {e}")
        
        self.config = config
        
        # Obter a chave de API
        self.api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.critical("Chave de API do OpenAI não configurada")
            raise ValueError("Chave de API do OpenAI é necessária. Configure via OPENAI_API_KEY ou no arquivo de configuração.")
        
        # Exibir os primeiros caracteres da API key (para debug)
        if self.api_key and len(self.api_key) > 8:
            masked_key = self.api_key[:4] + "..." + self.api_key[-4:]
            logger.debug(f"API Key configurada: {masked_key}")
        else:
            logger.warning("API Key parece estar em formato inválido")
        
        # Configurações do modelo e voz
        # Obter o modelo da configuração, com fallback para a variável de ambiente ou valor padrão
        self.model = config.get("model") or os.environ.get("OPENAI_MODEL") or "gpt-4o-realtime-preview"
        self.voice = config.get("voice", "alloy")
        self.personality_prompt = config.get("personality_prompt", 
                                            "Você é o Turrão, um assistente com personalidade forte, irreverente e humor ácido. " +
                                            "Seja teimoso e responda com sarcasmo e ironia, mantendo um tom assertivo mas sempre com humor picante.")
        
        # Inicializar cliente assíncrono
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        logger.info(f"Agente Realtime inicializado com modelo {self.model} e voz {self.voice}")
    
    async def start_conversation(self, 
                                audio_input_stream, 
                                audio_output_stream,
                                on_speech_recognized: Optional[Callable[[str], None]] = None,
                                on_response_started: Optional[Callable[[], None]] = None,
                                on_response_text: Optional[Callable[[str], None]] = None,
                                on_completion: Optional[Callable[[], None]] = None):
        """
        Inicia uma conversação de voz em tempo real.
        
        Args:
            audio_input_stream: Stream de áudio de entrada (do microfone)
            audio_output_stream: Stream de áudio de saída (para os alto-falantes)
            on_speech_recognized: Callback executado quando a fala é reconhecida
            on_response_started: Callback executado quando a resposta começa
            on_response_text: Callback executado para cada trecho de texto da resposta
            on_completion: Callback executado quando a conversação é concluída
            
        Raises:
            RuntimeError: Se ocorrer erro durante a comunicação com a API
        """
        try:
            # Mostra informações da SDK para debug
            logger.debug(f"OpenAI SDK versão: {openai.__version__}")
            logger.debug(f"Atributos disponíveis em AsyncOpenAI: {dir(self.client)}")
            logger.debug(f"Atributos disponíveis em beta: {dir(self.client.beta) if hasattr(self.client, 'beta') else 'beta não disponível'}")
            
            logger.info("Iniciando conversação em tempo real")
            
            # Usar a API beta.realtime
            logger.debug("Conectando à API Realtime")
            async with self.client.beta.realtime.connect(model=self.model) as connection:
                logger.debug("Conexão estabelecida!")
                
                # Configurar a sessão com prompt e modalidades para áudio
                logger.debug("Atualizando configuração da sessão")
                await connection.session.update(session={
                    'modalities': ['audio', 'text'],  # IMPORTANTE: Habilitar voz e texto
                    'instructions': self.personality_prompt,  # Parâmetro correto conforme API
                    'voice': self.voice,  # Definir a voz para saída de áudio
                    # Configuração de detecção de turnos de fala
                    'turn_detection': {
                        'type': 'server_vad',  # Voice Activity Detection
                        'silence_duration_ms': 1000,  # Tempo de silêncio para determinar fim da fala
                        'interrupt_response': True  # Permitir interrupção do assistente
                    }
                })
                logger.debug("Sessão configurada com sucesso")
                
                # Definir uma função para capturar eventos
                event_count = 0
                text_response = ""  # Armazenar a resposta completa
                
                async def process_events():
                    nonlocal event_count, text_response
                    logger.debug("Iniciando captura de eventos")
                    
                    try:
                        async for event in connection:
                            event_count += 1
                            logger.debug(f"Evento #{event_count} recebido: {event.type}")
                            
                            # Mostrar todos os atributos do evento (para debug)
                            event_attrs = {}
                            for attr in dir(event):
                                if not attr.startswith('_') and not callable(getattr(event, attr)):
                                    try:
                                        value = getattr(event, attr)
                                        event_attrs[attr] = str(value)
                                    except:
                                        event_attrs[attr] = "Não pôde ser acessado"
                            
                            logger.debug(f"Atributos do evento: {json.dumps(event_attrs, indent=2)}")
                            
                            # Eventos de VAD (Voice Activity Detection)
                            if event.type == "input_audio_buffer.speech_started":
                                logger.debug("Detecção de fala: Usuário começou a falar")
                            
                            elif event.type == "input_audio_buffer.speech_stopped":
                                logger.debug("Detecção de fala: Usuário parou de falar")
                            
                            # Eventos de reconhecimento de fala
                            elif event.type == "voice_to_text.message.content" and hasattr(event, 'content'):
                                if hasattr(event.content, 'text'):
                                    text = event.content.text
                                    logger.debug(f"Texto reconhecido: {text}")
                                    if on_speech_recognized:
                                        await asyncio.to_thread(on_speech_recognized, text)
                            
                            # Eventos de início de resposta
                            elif event.type == "response.start":
                                logger.debug("Resposta iniciada")
                                if on_response_started:
                                    await asyncio.to_thread(on_response_started)
                            
                            # Eventos de delta de texto
                            elif event.type == "response.text.delta" and hasattr(event, 'delta'):
                                text = event.delta
                                text_response += text  # Acumular resposta
                                logger.debug(f"TEXTO: {text}")
                                if on_response_text:
                                    # Chamar o callback assincronamente
                                    await asyncio.to_thread(on_response_text, text)
                            
                            # Eventos de chunks de áudio
                            elif event.type == "text_to_voice.chunk" and hasattr(event, 'chunk'):
                                logger.debug("Recebido chunk de áudio")
                                if audio_output_stream:
                                    # Escrever diretamente no stream de saída
                                    await audio_output_stream.write(event.chunk)
                            
                            # Finalização de resposta
                            elif event.type == "response.done":
                                logger.debug(f"Resposta concluída: {text_response}")
                                break
                                
                    except Exception as e:
                        logger.error(f"Erro ao processar eventos: {e}")
                        logger.error(traceback.format_exc())
                
                # Iniciar tarefa para capturar eventos
                logger.debug("Criando tarefa para processar eventos")
                event_task = asyncio.create_task(process_events())
                
                try:
                    # Configurar streaming de áudio bidirecional
                    logger.debug("Configurando streams de áudio")
                    
                    # Função para converter e codificar áudio em Base64 (formato PCM16)
                    def encode_audio_to_base64(audio_chunk):
                        import base64
                        import struct
                        
                        # Se o áudio já estiver em PCM16, apenas codificamos em Base64
                        # Caso contrário, precisaríamos converter primeiro
                        # (assumindo que o áudio de entrada já está em PCM16)
                        return base64.b64encode(audio_chunk).decode('ascii')
                    
                    # Enviar áudio de entrada (do microfone) para a API
                    async def stream_input_audio():
                        logger.debug("Iniciando stream de áudio de entrada")
                        
                        # Flag para controlar se estamos falando
                        is_speaking = False
                        silence_counter = 0
                        
                        while True:
                            try:
                                # Ler dados do stream de áudio de entrada (já em PCM16)
                                audio_chunk = await audio_input_stream.read(4096)  # Tamanho de chunk otimizado
                                
                                if not audio_chunk:
                                    await asyncio.sleep(0.01)  # Pequena pausa para não consumir CPU
                                    
                                    # Incrementar contador de silêncio quando não há dados
                                    if is_speaking:
                                        silence_counter += 1
                                        # Se silêncio por tempo suficiente, finalizar entrada
                                        if silence_counter > 100:  # ~1 segundo de silêncio
                                            logger.debug("Detectado fim da fala, finalizando entrada de áudio")
                                            # Enviar evento de commit para finalizar a entrada de áudio
                                            if hasattr(connection, 'send'):
                                                logger.debug("Enviando commit de áudio")
                                                await connection.send({
                                                    "type": "input_audio_buffer.commit"
                                                })
                                                
                                                # Aguardar um pouco para o processamento ocorrer
                                                await asyncio.sleep(0.5)
                                                
                                                # Solicitar resposta
                                                logger.debug("Solicitando resposta")
                                                await connection.send({
                                                    "type": "response.create"
                                                })
                                            elif hasattr(connection, 'conversation'):
                                                # Tentativa alternativa usando conversation
                                                await connection.conversation.completion.create()
                                            is_speaking = False
                                            silence_counter = 0
                                    
                                    continue
                                
                                # Resetar contador de silêncio quando há dados
                                silence_counter = 0
                                
                                # Se ainda não estávamos falando, marcar que começamos
                                if not is_speaking:
                                    is_speaking = True
                                    logger.debug("Detectado início da fala")
                                
                                # Codificar o áudio em Base64
                                base64_audio = encode_audio_to_base64(audio_chunk)
                                
                                # Registrar o tamanho do áudio para debug
                                logger.debug(f"Enviando chunk de áudio: {len(audio_chunk)} bytes")
                                
                                # Enviar chunk de áudio para a API usando o método correto
                                if hasattr(connection, 'input_audio'):
                                    # Tentativa usando input_audio
                                    await connection.input_audio.send_chunk(audio_chunk)
                                elif hasattr(connection, 'send_binary'):
                                    # Tentativa usando send_binary diretamente
                                    await connection.send_binary(audio_chunk)
                                elif hasattr(connection, 'send'):
                                    # Enviar o dicionário diretamente - não serializar para JSON
                                    message = {
                                        "type": "input_audio_buffer.append",
                                        "audio": base64_audio
                                    }
                                    logger.debug(f"Enviando mensagem via send: objeto com tipo {message['type']}")
                                    await connection.send(message)
                                elif hasattr(connection, 'conversation'):
                                    # Tentativa usando a API de conversa
                                    await connection.conversation.item.create(
                                        item={
                                            "type": "audio",
                                            "content": {
                                                "audio": base64_audio
                                            }
                                        }
                                    )
                                else:
                                    # Não encontramos método compatível
                                    methods = [attr for attr in dir(connection) if not attr.startswith('_') and callable(getattr(connection, attr))]
                                    logger.debug(f"Métodos disponíveis: {methods}")
                                    logger.error("Não foi possível encontrar um método para enviar áudio")
                            except Exception as e:
                                logger.error(f"Erro ao processar áudio de entrada: {e}")
                                logger.error(traceback.format_exc())
                                break
                    
                    # Iniciar task para streaming de áudio de entrada
                    input_stream_task = asyncio.create_task(stream_input_audio())
                    
                    # Aguardar pela tarefa de processamento de eventos
                    logger.debug("Aguardando eventos de voz com timeout de 60 segundos")
                    try:
                        await asyncio.wait_for(event_task, timeout=60.0)
                    except asyncio.TimeoutError:
                        logger.debug("Timeout na espera por eventos")
                    except Exception as e:
                        logger.error(f"Erro durante processamento de eventos: {e}")
                    finally:
                        # Certificar-se de cancelar todas as tarefas
                        if not input_stream_task.done():
                            input_stream_task.cancel()
                            logger.debug("Tarefa de streaming de entrada cancelada")
                        try:
                            await input_stream_task
                        except asyncio.CancelledError:
                            pass
                        if audio_output_stream:
                            logger.debug("Finalizando stream de saída")
                            # Não tenta fechar o stream, apenas registra que está finalizando
                            # O stream será fechado pelo gerenciador de conversação
                except Exception as e:
                    logger.error(f"Erro na configuração de streaming de áudio: {e}")
                    logger.error(traceback.format_exc())
            
            logger.info("Conversação em tempo real concluída")
            
            if on_completion:
                await asyncio.to_thread(on_completion)
                
        except Exception as e:
            logger.error(f"Erro geral na conversação em tempo real: {e}")
            logger.error(traceback.format_exc())
            raise RuntimeError(f"Falha na API Realtime do OpenAI: {e}")
    
    def set_personality(self, personality_prompt: str) -> None:
        """
        Define ou atualiza a personalidade do agente.
        
        Args:
            personality_prompt: Prompt de sistema que define a personalidade
        """
        self.personality_prompt = personality_prompt
        logger.debug(f"Personalidade do agente atualizada: {personality_prompt[:50]}...")
