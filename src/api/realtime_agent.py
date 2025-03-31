#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cliente para comunicação com a API Realtime do OpenAI com reprodução em tempo real.

Este módulo implementa um cliente que se comunica com a API Realtime do OpenAI,
enviando áudio e recebendo a resposta em tempo real, para ser reproduzida à medida
que os chunks são recebidos.

Agora com gravação inteligente que detecta quando o usuário para de falar!
"""

import asyncio
import base64
import json
import logging
import os
import sys
import time
from typing import Dict, List, Optional, Any, Callable

# Importações de terceiros
import numpy as np
import pyaudio
from openai import AsyncOpenAI

# Importação do reprodutor de áudio em tempo real
from src.audio.player_realtime import AudioPlayerRealtime
from src.audio.smart_recorder import SmartRecorder
from src.utils.config import load_config

# Configuração básica de logging
logger = logging.getLogger(__name__)

# Constantes para captura de áudio
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 24000  # Taxa de amostragem para API da OpenAI
CHUNK_SIZE = 1024
RECORD_SECONDS = 5  # Agora usado apenas como fallback

# Constantes para a API
API_URL = "wss://api.openai.com/v1/audio/speech"
MODEL = "whisper-1"
VOICE = "alloy"  # Vozes disponíveis: alloy, echo, fable, onyx, nova, shimmer


async def process_audio_request(recorder: Optional[SmartRecorder] = None) -> Dict[str, Any]:
    """
    Processa uma solicitação de áudio completa:
    1. Grava áudio do microfone com detecção inteligente de silêncio
    2. Envia para a API Realtime
    3. Reproduz a resposta em tempo real conforme os chunks são recebidos
    
    Args:
        recorder: Instância do SmartRecorder já calibrada (opcional)
    
    Returns:
        Dicionário com o resultado da operação
    """
    # Instanciar o reprodutor de áudio em tempo real
    audio_player = AudioPlayerRealtime(sample_rate=RATE)
    
    # Obter a chave de API
    config = load_config()
    api_key = config.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
    
    if not api_key:
        logger.error("Chave de API da OpenAI não encontrada na configuração")
        return {}
    
    # Inicializar cliente OpenAI
    client = AsyncOpenAI(api_key=api_key)
    
    # Inicializar o gravador inteligente ou usar o passado por parâmetro
    audio_buffer = bytearray()
    recording_completed = asyncio.Event()
    own_recorder = False
    
    # Callback quando a gravação for concluída
    def on_recording_complete(audio_data: bytes):
        nonlocal audio_buffer
        audio_buffer.extend(audio_data)
        recording_completed.set()
    
    # Usar o gravador fornecido ou criar um novo
    if recorder is None:
        recorder = SmartRecorder(sample_rate=RATE)
        own_recorder = True
    
    # Iniciar gravação inteligente
    recorder.start_recording(on_recording_complete)
    
    try:
        # Aguardar até que a gravação seja concluída
        await recording_completed.wait()
        
        # Converter para bytes
        audio_data = bytes(audio_buffer)
        
        # Verificar se temos dados de áudio
        if len(audio_data) == 0:
            logger.error("Nenhum dado de áudio foi capturado")
            return {}
            
        # Informações para debug
        audio_duration = len(audio_data) / (RATE * CHANNELS * 2)  # Duração em segundos
        logger.debug(f"Áudio capturado: {len(audio_data)} bytes ({audio_duration:.2f}s)")
    
        print("Conectando à API Realtime...")
        
        # Conectar à API
        async with client.beta.realtime.connect(model="gpt-4o-realtime-preview") as connection:
            print("Conexão estabelecida!")
            
            # Obter a personalidade do assistente da configuração
            personality = config.get("assistant", {}).get("personality", 
                "Você é o Turrão, um assistente com personalidade forte e irreverente. "
                "Responda com humor ácido e sarcasmo.")
            
            # Configurar a sessão
            await connection.session.update(session={
                'modalities': ['audio', 'text'],
                'instructions': personality,
                'voice': 'alloy',  
                'output_audio_format': 'pcm16'
            })
            print("Sessão configurada!")
            
            # Dividir o audio em chunks menores para envio
            chunk_size = 4096
            audio_chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data), chunk_size)]
            total_chunks = len(audio_chunks)
            
            print("Enviando áudio para a API...")
            
            # Verificar se já existe uma resposta ativa 
            try:
                # Tentar cancelar qualquer resposta ativa anterior
                await connection.send({"type": "response.cancel"})
                await asyncio.sleep(0.5)  # Pequena pausa para garantir que o cancelamento seja processado
            except Exception as e:
                # Ignorar erros de cancelamento - pode não haver resposta ativa para cancelar
                logger.debug(f"Aviso ao cancelar resposta: {e}")
                
            # Enviar chunks de áudio para a API
            for i, chunk in enumerate(audio_chunks):
                base64_audio = base64.b64encode(chunk).decode('ascii')
                
                await connection.send({
                    "type": "input_audio_buffer.append",
                    "audio": base64_audio
                })
                
                if i % 10 == 0 or i == total_chunks - 1:
                    sys.stdout.write(".")
                    sys.stdout.flush()
            
            # Finalizar entrada de áudio
            await connection.send({"type": "input_audio_buffer.commit"})
            print("\nÁudio enviado!")
            
            # Solicitar resposta
            await connection.send({"type": "response.create"})
            print("Aguardando resposta...")
            
            # Contadores para estatísticas
            event_count = 0
            audio_delta_count = 0
            text_delta_count = 0
            total_audio_bytes = 0
            text_response = ""
            last_audio_item_id = None
            
            # Processar eventos da resposta
            async for event in connection:
                event_count += 1
                
                # Processa cada tipo de evento
                event_type = getattr(event, 'type', None)
                
                # Verificar erros
                if event_type == "error":
                    # Ignorar erros específicos que sabemos que não são críticos
                    error_message = getattr(event, 'error', None)
                    if error_message:
                        error_code = getattr(error_message, 'code', '')
                        
                        # Ignorar erro de "conversation_already_has_active_response"
                        if 'conversation_already_has_active_response' in str(error_code):
                            logger.debug("Ignorando erro de resposta ativa já existente")
                            continue
                            
                        # Ignorar erro de buffer muito pequeno se já enviamos todo o áudio
                        if 'input_audio_buffer_commit_empty' in str(error_code):
                            logger.debug("Ignorando erro de buffer vazio - já processamos o áudio disponível")
                            continue
                            
                        # Ignorar erro de "sem resposta ativa para cancelar"
                        if 'response_cancel_not_active' in str(error_code):
                            logger.debug("Ignorando erro de cancelamento - não havia resposta ativa")
                            continue
                    
                    # Exibir outros erros que podem ser importantes
                    logger.error(f"Erro na API: {error_message}")
                    continue
                
                # Processar eventos de texto
                if event_type == "response.text.delta":
                    text_delta_count += 1
                    if hasattr(event, 'delta'):
                        text_response += event.delta
                
                # Processar especificamente os eventos de áudio delta
                elif event_type == "response.audio.delta":
                    try:
                        audio_delta_count += 1
                        
                        # Verificar se temos um novo item de áudio (nova resposta)
                        item_id = getattr(event, 'item_id', None)
                        if item_id and item_id != last_audio_item_id:
                            # Se mudou o item_id, resetar o contador de frames
                            audio_player.reset_frame_count()
                            last_audio_item_id = item_id
                        
                        # Obter os dados de áudio base64
                        audio_base64 = None
                        
                        if hasattr(event, 'delta'):
                            audio_base64 = event.delta
                        
                        if not audio_base64:
                            continue
                            
                        # Decodificar os dados de Base64
                        chunk_data = base64.b64decode(audio_base64)
                        
                        # Pular chunks vazios
                        if len(chunk_data) == 0:
                            continue
                        
                        # Adicionar o chunk ao reprodutor de áudio em tempo real
                        audio_player.add_audio_chunk(chunk_data)
                        
                        # Estatísticas
                        total_audio_bytes += len(chunk_data)
                        
                    except Exception as e:
                        logger.error(f"Erro ao processar áudio: {e}")
                
                # Finalização da resposta
                elif event_type == "response.done":
                    logger.debug("Evento final recebido.")
                    break
            
            print("\nResposta concluída!")
            
            print(f"\nTotal de eventos de áudio recebidos: {audio_delta_count} (Total: {total_audio_bytes} bytes)")
            
            # Garantir que todo o áudio tenha sido reproduzido
            if audio_delta_count > 0:
                print("Aguardando finalização da reprodução do áudio...")
                
                # Usar o novo método mais confiável para detectar o fim da reprodução
                max_wait_time = 30  # 30 segundos como tempo máximo de segurança
                start_wait = time.time()
                
                while not audio_player.is_playing_complete() and (time.time() - start_wait < max_wait_time):
                    await asyncio.sleep(0.1)
                    
                    # Feedback periódico para mostrar que ainda está processando
                    if (time.time() - start_wait) % 3 < 0.1:  # A cada ~3 segundos
                        sys.stdout.write(".")
                        sys.stdout.flush()
                
                # Se excedeu o timeout, avisar mas continuar
                if time.time() - start_wait >= max_wait_time:
                    print("\nTempo limite de segurança excedido. Finalizando mesmo assim.")
                else:
                    print("\nReprodução concluída com sucesso!")
            
            # Parar o reprodutor de áudio após a reprodução completa
            audio_player.stop_playback()
            
            # Retornar informações sobre a operação
            return {
                "success": True,
                "audio_events": audio_delta_count,
                "text_events": text_delta_count,
                "total_audio_bytes": total_audio_bytes,
                "text_response": text_response
            }
    
    except Exception as e:
        logger.error(f"Erro no processamento do áudio: {str(e)}")
        # Capturar e tratar erros específicos
        error_msg = str(e).lower()
        
        # Tentar cancelar a resposta (ignorar erros)
        try:
            if 'connection' in locals():
                await connection.send({"type": "response.cancel"})
        except Exception as cancel_error:
            # Ignorar especificamente erros de "no active response found"
            if "no active response found" in str(cancel_error).lower():
                logger.debug("Ignorando erro ao cancelar resposta (não há resposta ativa).")
            else:
                logger.error(f"Erro ao cancelar resposta: {cancel_error}")
        
        # Sempre parar o reprodutor de áudio em caso de erro
        if 'audio_player' in locals():
            audio_player.stop_playback()
            
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        # Parar o gravador apenas se foi criado aqui
        if own_recorder and 'recorder' in locals():
            recorder.stop_recording()


async def run_agent(recorder: Optional[SmartRecorder] = None) -> Dict[str, Any]:
    """
    Função principal para executar o agente de voz.
    
    Esta função executa todo o ciclo de uma interação com o assistente:
    1. Captura áudio inteligentemente do microfone até detectar silêncio
    2. Envia para a API Realtime da OpenAI
    3. Reproduz a resposta em tempo real
    
    Args:
        recorder: Instância do SmartRecorder já calibrada (opcional)
    
    Returns:
        Dicionário com o resultado da operação
    """
    print("=== AGENTE DE VOZ COM REPRODUÇÃO EM TEMPO REAL ===")
    print("Este agente vai gravar seu áudio até você parar de falar e enviar para a API.")
    
    try:
        return await process_audio_request(recorder)
    except Exception as e:
        logger.error(f"Erro ao executar o agente: {e}")
        return None