#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cliente para comunicação com a API Realtime do OpenAI.

Este módulo implementa um cliente que se comunica com a API Realtime do OpenAI,
encapsulando a lógica de conexão, envio de mensagens e manipulação de eventos.
"""

import asyncio
import base64
import json
import logging
import os
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator

from openai import AsyncOpenAI

from src.utils.config import load_config

logger = logging.getLogger(__name__)

class OpenAIRealtimeClient:
    """
    Cliente para comunicação com a API Realtime do OpenAI.
    
    Esta classe encapsula toda a comunicação com a API Realtime da OpenAI,
    fornecendo métodos para enviar áudio e receber respostas.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa o cliente OpenAI.
        
        Args:
            api_key: Chave de API da OpenAI (opcional, se não fornecida será buscada na configuração)
        """
        config = load_config()
        self.api_key = api_key or config.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
        
        if not self.api_key:
            logger.error("Chave de API da OpenAI não encontrada")
            raise ValueError("Chave de API da OpenAI é necessária")
            
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = config.get("openai", {}).get("model", "gpt-4o-realtime-preview")
        self.connection = None
        
    async def connect(self) -> None:
        """
        Estabelece conexão com a API Realtime.
        
        Note: Este método não é assíncrono. O método connect da OpenAI
        retorna um AsyncRealtimeConnectionManager que não é awaitable.
        """
        logger.debug(f"Conectando à API Realtime com modelo {self.model}...")
        self.connection = await self.client.beta.realtime.connect(model=self.model).enter()
        logger.debug("Conexão estabelecida!")
        
    async def configure_session(self, 
                               instructions: str, 
                               voice: str = "alloy", 
                               output_format: str = "pcm16",
                               modalities: List[str] = None) -> None:
        """
        Configura a sessão com a API Realtime.
        
        Args:
            instructions: Instruções para definir a personalidade do assistente
            voice: Voz a ser utilizada ('alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer')
            output_format: Formato de saída do áudio ('pcm16', 'opus', 'mp3', etc)
            modalities: Lista de modalidades ('audio', 'text')
        """
        if not self.connection:
            raise RuntimeError("Conexão não estabelecida. Chame connect() primeiro.")
            
        if modalities is None:
            modalities = ['audio', 'text']
            
        logger.debug(f"Configurando sessão: voz={voice}, formato={output_format}")
        
        await self.connection.session.update(session={
            'modalities': modalities,
            'instructions': instructions,
            'voice': voice,
            'output_audio_format': output_format
        })
        
        logger.debug("Sessão configurada com sucesso")
        
    async def send_audio(self, audio_data: bytes, chunk_size: int = 4096) -> None:
        """
        Envia áudio para a API Realtime.
        
        Args:
            audio_data: Dados de áudio em bytes
            chunk_size: Tamanho dos chunks para envio
        """
        if not self.connection:
            raise RuntimeError("Conexão não estabelecida. Chame connect() primeiro.")
            
        # Dividir o áudio em chunks menores para envio
        audio_chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data), chunk_size)]
        
        logger.debug(f"Enviando {len(audio_chunks)} chunks de áudio para a API...")
        
        # Tentar cancelar qualquer resposta ativa anterior
        try:
            await self.connection.send({"type": "response.cancel"})
            await asyncio.sleep(0.5)  # Pequena pausa para garantir que o cancelamento seja processado
        except Exception as e:
            # Ignorar erros de cancelamento - pode não haver resposta ativa para cancelar
            logger.debug(f"Aviso ao cancelar resposta: {e}")
            
        # Enviar chunks de áudio para a API
        for chunk in audio_chunks:
            base64_audio = base64.b64encode(chunk).decode('ascii')
            
            await self.connection.send({
                "type": "input_audio_buffer.append",
                "audio": base64_audio
            })
            
        # Finalizar entrada de áudio
        await self.connection.send({"type": "input_audio_buffer.commit"})
        logger.debug("Áudio enviado com sucesso")
        
    async def request_response(self) -> None:
        """
        Solicita uma resposta da API Realtime.
        """
        if not self.connection:
            raise RuntimeError("Conexão não estabelecida. Chame connect() primeiro.")
            
        await self.connection.send({"type": "response.create"})
        logger.debug("Solicitação de resposta enviada")
        
    async def process_events(self, 
                            on_audio_chunk: Optional[Callable[[bytes, str], None]] = None,
                            on_text_chunk: Optional[Callable[[str], None]] = None,
                            on_finish: Optional[Callable[[Dict[str, Any]], None]] = None,
                            on_error: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Processa eventos recebidos da API Realtime.
        
        Args:
            on_audio_chunk: Callback para lidar com chunks de áudio recebidos (opcional)
            on_text_chunk: Callback para lidar com chunks de texto recebidos (opcional)
            on_finish: Callback chamado quando o processamento é concluído (opcional)
            on_error: Callback para lidar com erros (opcional)
            
        Returns:
            Dicionário com os resultados do processamento (texto completo, estatísticas, etc)
        """
        if not self.connection:
            raise RuntimeError("Conexão não estabelecida. Chame connect() primeiro.")
            
        # Contadores para estatísticas
        event_count = 0
        audio_delta_count = 0
        text_delta_count = 0
        total_audio_bytes = 0
        text_response = ""
        last_audio_item_id = None
        
        # Processar eventos da resposta
        while True:
            try:
                event = await self.connection.recv()
            except asyncio.CancelledError:
                logger.warning("Processamento de eventos interrompido")
                break
            except Exception as e:
                logger.error(f"Erro ao processar eventos: {e}")
                break
            
            event_count += 1
            
            # Processa cada tipo de evento
            event_type = getattr(event, 'type', None)
            
            # Verificar erros
            if event_type == "error":
                # Ignorar erros específicos que sabemos que não são críticos
                error_message = getattr(event, 'error', None)
                if error_message:
                    error_code = getattr(error_message, 'code', '')
                    
                    # Ignorar erros conhecidos
                    if any(code in str(error_code) for code in 
                          ['conversation_already_has_active_response', 
                           'input_audio_buffer_commit_empty',
                           'response_cancel_not_active']):
                        logger.debug(f"Ignorando erro conhecido: {error_code}")
                        continue
                
                # Exibir outros erros que podem ser importantes
                logger.error(f"Erro na API: {error_message}")
                
                if on_error:
                    on_error({"error": error_message})
                    
                continue
            
            # Processar eventos de texto
            if event_type == "response.text_delta":
                delta = getattr(event, 'delta', None)
                if delta:
                    text_delta_count += 1
                    text_response += delta
                    
                    if on_text_chunk:
                        on_text_chunk(delta)
            
            # Processar eventos de áudio
            elif event_type == "response.audio_delta":
                delta = getattr(event, 'delta', None)
                item_id = getattr(event, 'item_id', None)
                
                if delta and delta.get('base64_audio'):
                    audio_delta_count += 1
                    
                    # Decodificar o áudio
                    audio_data = base64.b64decode(delta['base64_audio'])
                    total_audio_bytes += len(audio_data)
                    last_audio_item_id = item_id
                    
                    if on_audio_chunk:
                        on_audio_chunk(audio_data, item_id)
            
            # Processar evento de fim da resposta
            elif event_type == "response.done":
                logger.debug(f"Resposta concluída: {event_count} eventos, {audio_delta_count} chunks de áudio, {text_delta_count} chunks de texto")
                
                result = {
                    "text": text_response,
                    "events": event_count,
                    "audio_chunks": audio_delta_count,
                    "text_chunks": text_delta_count,
                    "total_audio_bytes": total_audio_bytes,
                    "last_audio_item_id": last_audio_item_id
                }
                
                if on_finish:
                    on_finish(result)
                    
                return result
                
        # Retornar resultados parciais se o loop for interrompido sem evento done
        logger.warning("Processamento de eventos interrompido sem evento de conclusão")
        
        result = {
            "text": text_response,
            "events": event_count,
            "audio_chunks": audio_delta_count,
            "text_chunks": text_delta_count,
            "total_audio_bytes": total_audio_bytes,
            "last_audio_item_id": last_audio_item_id,
            "completed": False
        }
        
        if on_finish:
            on_finish(result)
            
        return result

    async def close(self) -> None:
        """
        Fecha a conexão com a API Realtime.
        """
        
        logger.debug("Conexão fechada")
        self.connection = None
