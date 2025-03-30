#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Teste focado exclusivamente nos eventos response.audio.delta da API Realtime.
Esse script ignora todo o processamento de áudio e apenas salva os eventos brutos
para análise e troubleshooting.
"""

import asyncio
import base64
import os
import sys
import time
import json
import logging
import traceback
import io
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("audio_only_test")

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
RATE = 16000
CHUNK_SIZE = 4096
RECORD_SECONDS = 3

# Diretório para salvar os arquivos
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Função simplificada para reproduzir áudio diretamente
def play_audio_sync(audio_bytes):
    """
    Reproduz áudio PCM diretamente usando sounddevice.
    
    Args:
        audio_bytes: Dados de áudio PCM em bytes
    """
    try:
        # Converter os bytes para um array numpy
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Parâmetros de áudio
        samplerate = RATE
        
        # Reproduzir os dados de áudio
        sd.play(audio_np, samplerate=samplerate)
        
        # Esperar até que a reprodução termine
        # Para não bloquear, não usamos sd.wait() aqui
        logger.info(f"Reproduzindo {len(audio_bytes)} bytes de áudio")
        return True
    except Exception as e:
        logger.error(f"Erro ao reproduzir áudio: {e}")
        return False

# Função simplificada para reproduzir áudio de forma assíncrona
async def play_audio(audio_bytes):
    """
    Versão assíncrona da função de reprodução de áudio.
    
    Args:
        audio_bytes: Dados de áudio PCM em bytes
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, play_audio_sync, audio_bytes)


async def test_audio_events():
    """Testa especificamente os eventos de áudio da API Realtime."""
    try:
        # Obter chave da API do ambiente
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            api_key = input("Digite sua chave de API da OpenAI: ")
            if not api_key:
                logger.error("Chave de API é necessária para o teste")
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
        
        # Capturar alguns segundos de áudio antes de iniciar
        print("Gravando áudio...")
        audio_data = bytearray()
        for _ in range(0, int(RATE / CHUNK_SIZE * RECORD_SECONDS)):
            data = stream_in.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data.extend(data)
            sys.stdout.write(".")
            sys.stdout.flush()
        print("\nGravação concluída!")
        
        # Fechar stream de entrada
        stream_in.stop_stream()
        stream_in.close()
        
        # Conectar à API Realtime
        print("Conectando à API Realtime...")
        
        # Lista para armazenar todos os eventos e dados de áudio
        all_audio_deltas = []
        
        async with client.beta.realtime.connect(model="gpt-4o-realtime-preview") as connection:
            print("Conexão estabelecida!")
            
            # Configurar a sessão
            await connection.session.update(session={
                'modalities': ['audio', 'text'],
                'instructions': "Você é o Turrão, um assistente com personalidade forte e irreverente. "
                               "Responda com humor ácido. Diga 'TESTE DE ÁUDIO FUNCIONANDO' em algum momento da sua resposta.",
                'voice': 'alloy',
                'output_audio_format': 'pcm16'
            })
            
            logger.info("Configuração da sessão:")
            logger.info("- Modalidades: audio, text")
            logger.info("- Formato de áudio: pcm16")
            logger.info("- Voz: alloy")
            
            print("Sessão configurada!")
            
            # Enviar o áudio gravado anteriormente em chunks
            logger.info(f"Enviando {len(audio_data)} bytes de áudio para a API")
            chunk_size = 4096
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
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
            
            # Arquivo para salvar todos os eventos raw
            events_file = OUTPUT_DIR / "raw_events.json"
            raw_events = []
            
            # Arquivo para salvar os deltas de áudio concatenados
            audio_file = OUTPUT_DIR / "audio_deltas_raw.pcm"
            audio_data = bytearray()
            
            # Contar eventos de áudio
            audio_delta_count = 0
            
            # Flag para verificar se estamos recebendo os eventos
            found_audio_delta = False
            
            # Processar eventos por até 30 segundos
            start_time = time.time()
            timeout = 30
            
            # Lista para armazenar todos os tipos de eventos recebidos para diagnóstico
            received_event_types = []
            
            try:
                async for event in connection:
                    event_type = getattr(event, 'type', None)
                    logger.debug(f"Evento recebido: {event_type}")
                    
                    # Adicionar ao registro de tipos de eventos
                    received_event_types.append(event_type)
                    
                    # Registrar todos os eventos para debug
                    event_data = {"type": event_type}
                    
                    # Adicionar atributos do evento ao registro
                    for attr in dir(event):
                        if not attr.startswith('_') and not callable(getattr(event, attr)):
                            try:
                                value = getattr(event, attr)
                                if attr == 'audio' and value:
                                    # Para 'audio', registramos o tamanho nos logs
                                    event_data[attr] = f"[{len(value)} bytes]"
                                elif isinstance(value, (str, int, float, bool)) or value is None:
                                    event_data[attr] = value
                                else:
                                    event_data[attr] = str(value)
                            except Exception as attr_error:
                                event_data[attr] = f"Error: {attr_error}"
                    
                    raw_events.append(event_data)
                    
                    # Processar especificamente os eventos de áudio delta
                    if event_type == "response.audio.delta":
                        audio_delta_count += 1
                        found_audio_delta = True
                        
                        try:
                            # O importante aqui é acessar a propriedade correta 'delta' em vez de 'audio'
                            # De acordo com o exemplo de implementação
                            audio_base64 = None
                            
                            # Verificar se o evento tem a propriedade 'delta'
                            if hasattr(event, 'delta'):
                                audio_base64 = event.delta
                                logger.info(f"Obtido áudio via event.delta: {len(audio_base64)} bytes")
                            # Alternativa: tentar acessar como dicionário
                            elif hasattr(event, '__dict__'):
                                event_dict = event.__dict__
                                if 'delta' in event_dict:
                                    audio_base64 = event_dict['delta']
                                    logger.info(f"Obtido áudio via event.__dict__['delta']: {len(audio_base64)} bytes")
                            
                            if not audio_base64:
                                logger.warning("Evento de áudio sem dados de delta")
                                continue
                                
                            # Decodificar os dados de Base64
                            audio_bytes = base64.b64decode(audio_base64)
                            
                            # Pular chunks vazios
                            if len(audio_bytes) == 0:
                                logger.warning("Chunk de áudio vazio recebido")
                                continue
                                
                            # Adicionar ao buffer para salvar posteriormente
                            audio_data.extend(audio_bytes)
                            
                            # MÉTODO 1: Reproduzir diretamente com sounddevice (mais simples)
                            logger.info(f"Reproduzindo chunk de áudio {audio_delta_count} ({len(audio_bytes)} bytes)")
                            await play_audio(audio_bytes)
                            
                            # Registrar detalhes
                            logger.info(f"Áudio delta #{audio_delta_count}: {len(audio_bytes)} bytes")
                            
                            # Mostrar alguns bytes para debug
                            if len(audio_bytes) > 0:
                                first_bytes = ' '.join([f'{b:02x}' for b in audio_bytes[:8]])
                                logger.debug(f"Primeiros bytes: {first_bytes}")
                            
                            # Indicador visual
                            sys.stdout.write("")
                            sys.stdout.flush()
                            
                        except Exception as e:
                            logger.error(f"Erro ao processar áudio: {e}")
                            logger.error(traceback.format_exc())
                    
                    # Finalização da resposta
                    elif event_type == "response.done":
                        logger.info("Resposta concluída")
                        break
                    
                    # Timeout
                    if time.time() - start_time > timeout:
                        logger.warning(f"Timeout após {timeout} segundos")
                        break
                
            except Exception as e:
                logger.error(f"Erro ao processar eventos: {e}")
                logger.error(traceback.format_exc())
            
            # Resumo de diagnóstico
            logger.info(f"Tipos de eventos recebidos: {received_event_types}")
            logger.info(f"Total de eventos: {len(raw_events)}")
            
            # Salvar todos os eventos para análise
            with open(events_file, 'w', encoding='utf-8') as f:
                json.dump(raw_events, f, indent=2)
            
            # Salvar os dados de áudio concatenados
            if len(audio_data) > 0:
                with open(audio_file, 'wb') as f:
                    f.write(audio_data)
                
                logger.info(f"Arquivo de áudio salvo: {audio_file} ({len(audio_data)} bytes)")
                print(f"\nArquivo de áudio salvo: {audio_file}")
            else:
                logger.warning("Nenhum dado de áudio recebido para salvar")
                print("\nNenhum dado de áudio recebido para salvar")
            
            # Resumo dos eventos de áudio
            print(f"\nTotal de eventos response.audio.delta: {audio_delta_count}")
            if found_audio_delta:
                print("Eventos de áudio detectados")
            else:
                print("Nenhum evento de áudio detectado")
            
            # Informações finais
            print(f"\nEventos salvos em: {events_file}")
            print("\nPara reproduzir o arquivo PCM raw, você pode usar:")
            print(f"ffplay -f s16le -ar 16000 {audio_file}")
            print("ou")
            print(f"vlc --demux=rawaud --rawaud-samplerate=16000 {audio_file}")
            
            logger.info("Teste concluído com sucesso")
    
    except Exception as e:
        logger.error(f"Erro durante o teste: {e}")
        logger.error(traceback.format_exc())
        print(f"\nErro: {e}")


if __name__ == "__main__":
    print("=== TESTE EXCLUSIVO DE EVENTOS DE ÁUDIO DA API REALTIME ===")
    print("Este teste vai gravar áudio, enviar para a API e salvar os eventos")
    print("de áudio recebidos para análise posterior.")
    print("\nPressione Enter para iniciar...")
    input()
    
    try:
        asyncio.run(test_audio_events())
    except Exception as e:
        logger.error(f"Erro na execução: {e}")
        logger.error(traceback.format_exc())
        print(f"Erro na execução: {e}")
