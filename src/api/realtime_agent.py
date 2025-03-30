#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cliente simplificado para comunicação com a API Realtime do OpenAI.

Este módulo implementa uma versão simplificada do agente que:
1. Grava áudio por um tempo fixo (5 segundos)
2. Envia para a API Realtime
3. Reproduz a resposta de áudio
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

# Importar dependências
try:
    import pyaudio
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    from openai import AsyncOpenAI
except ImportError as e:
    logger.error(f"Erro ao importar bibliotecas: {e}")
    logger.error("Instale as dependências com: pip install pyaudio numpy openai sounddevice soundfile")
    sys.exit(1)

# Configurações
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Taxa de amostragem para a captura
OUTPUT_RATE = 24000  # Taxa de amostragem para a reprodução da API OpenAI
CHUNK_SIZE = 4096
RECORD_SECONDS = 5  # Tempo de gravação fixo em 5 segundos


# Função para reproduzir áudio completo
def play_audio(audio_bytes, samplerate=24000):
    """
    Reproduz o áudio usando sounddevice.
    
    Args:
        audio_bytes: Dados de áudio em bytes
        samplerate: Taxa de amostragem
    """
    try:
        # Converter bytes para array numpy
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        
        print(f"\nReproduzindo resposta de áudio ({len(audio_bytes)} bytes)...")
        
        # Reproduzir áudio
        sd.play(audio_np, samplerate=samplerate)
        sd.wait()  # Aguardar o áudio terminar
        
        print("Reprodução concluída.")
        return True
    except Exception as e:
        logger.error(f"Erro ao reproduzir áudio: {e}")
        logger.error(traceback.format_exc())
        return False


async def process_audio_request():
    """
    Processa uma solicitação de áudio completa:
    1. Grava áudio do microfone por um tempo fixo
    2. Envia para a API Realtime
    3. Coleta toda a resposta de áudio
    4. Reproduz o áudio completo de uma vez
    """
    try:
        # Obter chave da API do ambiente
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("Chave de API da OpenAI não encontrada no ambiente")
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
        all_audio_chunks = []  # Armazenar todos os chunks de áudio
        
        async with client.beta.realtime.connect(model="gpt-4o-realtime-preview") as connection:
            print("Conexão estabelecida!")
            
            # Configurar a sessão
            await connection.session.update(session={
                'modalities': ['audio', 'text'],
                'instructions': "Você é o Turrão, um assistente com personalidade forte e irreverente. "
                               "Responda com humor ácido e sarcasmo.",
                'voice': 'alloy',
                'output_audio_format': 'pcm16'
            })
            
            print("Sessão configurada!")
            
            # Enviar o áudio gravado anteriormente em chunks
            print(f"Enviando áudio para a API...")
            chunk_size = 4096
            
            # Converter lista de chunks em um único bytearray
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
            print("Aguardando resposta...")
            
            # Contadores para monitoramento
            audio_delta_count = 0
            total_audio_bytes = 0
            
            # Processar eventos
            async for event in connection:
                event_type = getattr(event, 'type', None)
                
                # Processar eventos de texto
                if event_type == "response.text.delta":
                    if hasattr(event, 'delta'):
                        texto_resposta += event.delta
                        print(event.delta, end="", flush=True)
                
                # Processar especificamente os eventos de áudio delta
                elif event_type == "response.audio.delta":
                    try:
                        audio_delta_count += 1
                        
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
                        
                        # Guardar o chunk para reprodução posterior
                        all_audio_chunks.append(audio_bytes)
                        total_audio_bytes += len(audio_bytes)
                        
                    except Exception as e:
                        logger.error(f"Erro ao processar áudio: {e}")
                
                # Finalização da resposta
                elif event_type == "response.done":
                    print("\nResposta concluída!")
                    break
            
            print(f"Total de eventos de áudio recebidos: {audio_delta_count} (Total: {total_audio_bytes} bytes)")
            
            # Concatenar todos os chunks de áudio em um único buffer
            if all_audio_chunks:
                all_audio = bytearray()
                for chunk in all_audio_chunks:
                    all_audio.extend(chunk)
                
                # Reproduzir todo o áudio de uma vez
                play_audio(all_audio, samplerate=OUTPUT_RATE)
            else:
                print("Nenhum áudio recebido para reprodução.")
            
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
    print("=== AGENTE DE VOZ SIMPLIFICADO ===")
    print(f"Este agente vai gravar {RECORD_SECONDS} segundos de áudio e enviar para a API.")
    
    resultado = await process_audio_request()
    if resultado:
        return resultado
    else:
        logger.error("Falha ao processar solicitação de áudio")
        return None