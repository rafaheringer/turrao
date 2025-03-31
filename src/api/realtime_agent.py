#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cliente para comunicação com a API Realtime do OpenAI com reprodução em tempo real.

Este módulo implementa um agente que:
1. Grava áudio por um tempo fixo (5 segundos)
2. Envia para a API Realtime
3. Reproduz a resposta de áudio em tempo real, enquanto os chunks são recebidos
"""

import asyncio
import base64
import os
import sys
import time
import logging
import traceback
from pathlib import Path

# Adicionar o diretório raiz ao Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Configurar logging - Reduzido para WARNING para minimizar saída
logging.basicConfig(
    level=logging.WARNING,  # Alterado de INFO para WARNING para reduzir ainda mais os logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configurar logging para outros módulos
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

logger = logging.getLogger("realtime_agent")
logger.setLevel(logging.INFO)  # Mantém INFO apenas para nosso módulo

# Importar módulo de configuração
from src.utils.config import load_config

# Carregar configurações
config = load_config()

# Importar dependências
try:
    import pyaudio
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    from openai import AsyncOpenAI
    
    # Importar nosso reprodutor de áudio em tempo real
    from src.audio.player_realtime import AudioPlayerRealtime
except ImportError as e:
    logger.error(f"Erro ao importar bibliotecas: {e}")
    logger.error("Instale as dependências com: pip install pyaudio numpy openai sounddevice soundfile")
    sys.exit(1)

# Configurações
FORMAT = pyaudio.paInt16
CHANNELS = config["audio"]["channels"]
RATE = config["audio"]["sample_rate"]  # Taxa de amostragem para a captura
OUTPUT_RATE = 24000  # Taxa de amostragem para a reprodução da API OpenAI
CHUNK_SIZE = config["audio"]["chunk_size"]
RECORD_SECONDS = 5  # Tempo de gravação fixo em 5 segundos


async def process_audio_request():
    """
    Processa uma solicitação de áudio completa:
    1. Grava áudio do microfone por um tempo fixo
    2. Envia para a API Realtime
    3. Reproduz a resposta em tempo real conforme os chunks são recebidos
    """
    try:
        # Obter chave da API da configuração
        api_key = config["api"].get("api_key")
        if not api_key:
            logger.error("Chave de API da OpenAI não encontrada na configuração")
            return
        
        # Inicializar cliente OpenAI
        client = AsyncOpenAI(api_key=api_key)
        
        # Inicializar PyAudio para captura
        audio = pyaudio.PyAudio()
        stream_in = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        # Capturar alguns segundos de áudio
        print(f"Gravando áudio por {RECORD_SECONDS} segundos...")
        audio_data = []
        for _ in range(0, int(RATE / CHUNK_SIZE * RECORD_SECONDS)):
            data = stream_in.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data.append(data)
            sys.stdout.write(".")
            sys.stdout.flush()
        print("\nGravação concluída!")
        
        # Fechar stream de entrada
        stream_in.stop_stream()
        stream_in.close()
        audio.terminate()
        
        # Conectar à API Realtime
        print("Conectando à API Realtime...")
        
        # Armazenar a resposta
        texto_resposta = ""
        
        # Inicializar o reprodutor de áudio em tempo real
        audio_player = AudioPlayerRealtime(sample_rate=OUTPUT_RATE, channels=CHANNELS)
        
        # Variáveis para controle e estatísticas
        audio_delta_count = 0
        total_audio_bytes = 0
        last_audio_item_id = None
        
        # Obter o modelo da configuração ou usar o padrão
        model = config["api"].get("model", "gpt-4o-realtime-preview")
        
        async with client.beta.realtime.connect(model=model) as connection:
            print("Conexão estabelecida!")
            
            # Obter a personalidade do assistente da configuração
            personality = config["assistant"].get("personality", 
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
            
            # Enviar o áudio gravado anteriormente em chunks
            print(f"Enviando áudio para a API...")
            chunk_size = 4096
            
            # Converter lista de chunks em um único bytearray para facilitar o fatiamento
            audio_data_combined = bytearray(b''.join(audio_data))
            
            for i in range(0, len(audio_data_combined), chunk_size):
                chunk = audio_data_combined[i:i+chunk_size]
                base64_audio = base64.b64encode(chunk).decode('ascii')
                
                await connection.send({
                    "type": "input_audio_buffer.append",
                    "audio": base64_audio
                })
                sys.stdout.write(".")
                sys.stdout.flush()
            
            # Finalizar entrada de áudio
            await connection.send({"type": "input_audio_buffer.commit"})
            print("\nÁudio enviado!")
            
            # Solicitar resposta
            await connection.send({"type": "response.create"})
            print("Aguardando resposta...\n")
            
            # Processar eventos
            async for event in connection:
                event_type = getattr(event, 'type', None)
                
                # Verificar erros
                if event_type == "error":
                    print(f"Erro na API: ", end="")
                    if hasattr(event, 'error'):
                        print(f"{event.error}")
                    continue
                
                # Processar eventos de texto
                if event_type == "response.text.delta":
                    if hasattr(event, 'delta'):
                        texto_resposta += event.delta
                        print(event.delta, end="", flush=True)
                
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
                        audio_bytes = base64.b64decode(audio_base64)
                        
                        # Pular chunks vazios
                        if len(audio_bytes) == 0:
                            continue
                        
                        # Adicionar o chunk ao reprodutor de áudio em tempo real
                        audio_player.add_audio_chunk(audio_bytes)
                        
                        # Estatísticas
                        total_audio_bytes += len(audio_bytes)
                        
                        # Visual feedback para mostrar que estamos recebendo áudio
                        if audio_delta_count % 5 == 0:  # Mostrar indicador a cada 5 chunks
                            sys.stdout.write("")
                            sys.stdout.flush()
                        
                    except Exception as e:
                        logger.error(f"Erro ao processar áudio: {e}")
                
                # Finalização da resposta
                elif event_type == "response.done":
                    print("\n\nResposta concluída!")
                    break
            
            print(f"\nTotal de eventos de áudio recebidos: {audio_delta_count} (Total: {total_audio_bytes} bytes)")
            
            # Garantir que todo o áudio tenha sido reproduzido
            # Aguardar um pouco para que o buffer possa ser consumido completamente
            if audio_delta_count > 0:
                print("Aguardando finalização da reprodução do áudio...")
                while not audio_player.is_buffer_empty():
                    await asyncio.sleep(0.1)
            
            # Parar o reprodutor de áudio após a reprodução completa
            audio_player.stop_playback()
            
            return {
                'text_response': texto_resposta
            }
    
    except Exception as e:
        logger.error(f"Erro durante o processamento: {e}")
        logger.error(traceback.format_exc())
        print(f"\nErro: {e}")
        return None


# Função principal para ser chamada de main.py
async def run_agent():
    """Função principal para executar o agente de voz"""
    print("=== AGENTE DE VOZ COM REPRODUÇÃO EM TEMPO REAL ===")
    print(f"Este agente vai gravar {RECORD_SECONDS} segundos de áudio e enviar para a API.")
    
    resultado = await process_audio_request()
    if resultado:
        return resultado
    else:
        logger.error("Falha ao processar solicitação de áudio")
        return None