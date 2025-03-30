#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Teste simples da API Realtime da OpenAI.

Este script cria uma conexão com a API Realtime da OpenAI,
captura áudio por alguns segundos e envia para a API,
recebendo e reproduzindo a resposta.
"""

import asyncio
import base64
import os
import sys
import time
import json
import logging
from typing import List, Dict, Any

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("realtime_test")

# Importar dependências
try:
    import pyaudio
    import numpy as np
    from openai import AsyncOpenAI
except ImportError as e:
    logger.error(f"Erro ao importar bibliotecas: {e}")
    logger.error("Instale as dependências com: pip install pyaudio numpy openai")
    sys.exit(1)

# Configurações de áudio
CHUNK_SIZE = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Taxa de amostragem em Hz (16kHz para API Realtime)
RECORD_SECONDS = 5  # Tempo de gravação


async def test_realtime_api():
    """Testa a API Realtime com áudio ao vivo."""
    try:
        # Obter chave da API do ambiente ou solicitar ao usuário
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            api_key = input("Digite sua chave de API da OpenAI: ")
            if not api_key:
                logger.error("Chave de API é necessária para o teste")
                return
        
        # Inicializar cliente OpenAI
        logger.info("Inicializando cliente OpenAI")
        client = AsyncOpenAI(api_key=api_key)
        
        # Verificar informações sobre o cliente
        logger.debug(f"Versão da SDK: {getattr(client, '__version__', 'Não disponível')}")
        
        # Inicializar PyAudio para captura
        audio = pyaudio.PyAudio()
        
        # Abrir stream para captura de áudio
        stream_in = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        # Abrir stream para reprodução
        stream_out = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True
        )
        
        # Conectar à API Realtime
        logger.info("Conectando à API Realtime")
        print("Conectando à API Realtime...")
        
        async with client.beta.realtime.connect(model="gpt-4o-realtime-preview") as connection:
            logger.info("Conexão estabelecida com sucesso!")
            print("✅ Conexão estabelecida!")
            
            # Configurar a sessão
            await connection.session.update(session={
                'modalities': ['audio', 'text'],
                'instructions': "Você é o Turrão, um assistente pessoal com personalidade forte, "
                               "irreverente e humor ácido. Seja teimoso e responda com sarcasmo e ironia, "
                               "mantendo um tom assertivo mas sempre com humor picante.",
                'voice': 'alloy',
                'output_audio_format': 'pcm16',
                'turn_detection': {
                    'type': 'server_vad',
                    'silence_duration_ms': 1000,
                    'interrupt_response': True
                }
            })
            logger.info("Sessão configurada com sucesso")
            print("✅ Sessão configurada!")
            
            print("🎤 FALE AGORA! Gravando por 5 segundos...")
            
            # Capturar e enviar chunks de áudio
            audio_fragments = []
            start_time = time.time()
            
            # Print dos métodos disponíveis para debug
            methods = [attr for attr in dir(connection) if not attr.startswith('_') and callable(getattr(connection, attr))]
            logger.debug(f"Métodos disponíveis na conexão: {methods}")
            
            # Capturar áudio e enviar à API
            while time.time() - start_time < RECORD_SECONDS:
                # Capturar chunk de áudio
                audio_chunk = stream_in.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_fragments.append(audio_chunk)
                
                # Codificar em Base64
                base64_audio = base64.b64encode(audio_chunk).decode('ascii')
                
                # Enviar para a API
                try:
                    event = {
                        "type": "input_audio_buffer.append",
                        "audio": base64_audio
                    }
                    await connection.send(event)
                    sys.stdout.write(".")
                    sys.stdout.flush()
                except Exception as e:
                    logger.error(f"Erro ao enviar áudio: {e}")
                
                # Pequena pausa para não sobrecarregar
                await asyncio.sleep(0.01)
            
            print("\n✅ Gravação concluída!")
            
            # Finalizar entrada de áudio
            try:
                logger.info("Enviando commit de áudio")
                await connection.send({"type": "input_audio_buffer.commit"})
                
                # Solicitar resposta
                logger.info("Solicitando resposta")
                await connection.send({"type": "response.create"})
            except Exception as e:
                logger.error(f"Erro ao solicitar resposta: {e}")
            
            # Processar eventos de resposta
            logger.info("Aguardando resposta...")
            print("🔊 Aguardando resposta do Turrão...")
            
            response_chunks = []
            audio_response = b""
            
            # Processar eventos por até 30 segundos
            start_time = time.time()
            timeout = 30  # 30 segundos de timeout
            
            try:
                async for event in connection:
                    event_type = getattr(event, 'type', None)
                    logger.debug(f"Evento recebido: {event_type}")
                    
                    # Registrar detalhes do evento para debug
                    event_attrs = {}
                    for attr in dir(event):
                        if not attr.startswith('_') and not callable(getattr(event, attr)):
                            try:
                                value = getattr(event, attr)
                                event_attrs[attr] = str(value)
                            except:
                                event_attrs[attr] = "Não pôde ser acessado"
                    
                    logger.debug(f"Atributos do evento: {json.dumps(event_attrs, indent=2)}")
                    
                    # Processar texto da resposta
                    if event_type == "response.text.delta" and hasattr(event, 'delta'):
                        text = event.delta
                        response_chunks.append(text)
                        print(text, end='', flush=True)
                    
                    # Processar áudio da resposta
                    elif event_type == "text_to_voice.chunk" and hasattr(event, 'chunk'):
                        audio_chunk = event.chunk
                        stream_out.write(audio_chunk)
                        audio_response += audio_chunk
                    
                    # Processar áudio da resposta - formato alternativo
                    elif event_type == "response.audio.chunk" and hasattr(event, 'audio'):
                        # API pode enviar áudio em formato Base64
                        try:
                            audio_bytes = base64.b64decode(event.audio)
                            stream_out.write(audio_bytes)
                            audio_response += audio_bytes
                            logger.debug(f"Reproduzindo chunk de áudio: {len(audio_bytes)} bytes")
                        except Exception as e:
                            logger.error(f"Erro ao processar chunk de áudio: {e}")
                    
                    # Processar áudio da resposta - formato delta (mais comum)
                    elif event_type == "response.audio.delta" and hasattr(event, 'audio'):
                        try:
                            audio_bytes = base64.b64decode(event.audio)
                            stream_out.write(audio_bytes)
                            audio_response += audio_bytes
                            logger.debug(f"Reproduzindo delta de áudio: {len(audio_bytes)} bytes")
                        except Exception as e:
                            logger.error(f"Erro ao processar delta de áudio: {e}")
                    
                    # Finalização da resposta
                    elif event_type == "response.done":
                        logger.info("Resposta concluída")
                        print("\n✅ Resposta concluída!")
                        break
                    
                    # Timeout para evitar loop infinito
                    if time.time() - start_time > timeout:
                        logger.warning(f"Timeout após {timeout} segundos")
                        print(f"\n⚠️ Timeout após {timeout} segundos")
                        break
            
            except Exception as e:
                logger.error(f"Erro ao processar resposta: {e}")
                logger.error(traceback.format_exc())
        
        # Fechar streams de áudio
        stream_in.stop_stream()
        stream_in.close()
        stream_out.stop_stream()
        stream_out.close()
        audio.terminate()
        
        logger.info("Teste concluído com sucesso")
        print("\n✅ Teste da API Realtime concluído!")
    
    except Exception as e:
        logger.error(f"Erro durante o teste: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"\n❌ Erro: {e}")
    
    finally:
        # Limpar recursos se necessário
        logger.info("Teste finalizado")


if __name__ == "__main__":
    # Executar o teste
    print("=== TESTE DA API REALTIME DA OPENAI ===")
    print("Este teste irá gravar 5 segundos de áudio e enviá-lo para a API Realtime.")
    print("A resposta será reproduzida em áudio e texto.")
    print("Pressione Enter para iniciar...")
    input()
    
    import traceback
    try:
        asyncio.run(test_realtime_api())
    except Exception as e:
        logger.error(f"Erro na execução: {e}")
        logger.error(traceback.format_exc())
        print(f"❌ Erro na execução: {e}")
