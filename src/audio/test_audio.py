#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Teste simples de captura e reprodução de áudio.

Este script captura áudio do microfone por 5 segundos e em seguida
reproduz o áudio capturado, para testar se a entrada e saída de áudio
estão funcionando corretamente.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("audio_test")

# Tentar importar bibliotecas de áudio
try:
    import pyaudio
    import numpy as np
except ImportError as e:
    logger.error(f"Erro ao importar bibliotecas: {e}")
    logger.error("Instale as dependências com: pip install pyaudio numpy")
    sys.exit(1)

# Definições para captura de áudio
CHUNK_SIZE = 4096
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Taxa de amostragem em Hz (16kHz é comum para reconhecimento de voz)
RECORD_SECONDS = 5


async def test_audio_capture_playback():
    """Captura áudio por 5 segundos e depois reproduz."""
    try:
        logger.info("Iniciando teste de áudio")
        
        # Inicializar PyAudio
        audio = pyaudio.PyAudio()
        logger.info("PyAudio inicializado")
        
        # Listar dispositivos disponíveis para debug
        info = audio.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        
        logger.info(f"Dispositivos de áudio disponíveis ({num_devices}):")
        for i in range(num_devices):
            device_info = audio.get_device_info_by_host_api_device_index(0, i)
            logger.info(f" - #{i}: {device_info.get('name')}")
            logger.info(f"   Input channels: {device_info.get('maxInputChannels')}")
            logger.info(f"   Output channels: {device_info.get('maxOutputChannels')}")
        
        # Abrir stream para captura
        logger.info("Abrindo stream para captura de áudio")
        stream_in = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        # Armazenar frames de áudio
        frames = []
        
        # Indicar que estamos gravando
        logger.info(f"Gravando áudio por {RECORD_SECONDS} segundos...")
        print("🎤 FALE AGORA! Gravando por 5 segundos...")
        
        # Capturar áudio por 5 segundos
        start_time = time.time()
        while time.time() - start_time < RECORD_SECONDS:
            data = stream_in.read(CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            # Mostrar um indicador visual de progresso
            sys.stdout.write(".")
            sys.stdout.flush()
            await asyncio.sleep(0.01)  # Pequena pausa para não bloquear
        
        print("\n✅ Gravação concluída!")
        logger.info("Gravação concluída")
        
        # Fechar stream de entrada
        stream_in.stop_stream()
        stream_in.close()
        
        # Abrir stream para reprodução
        logger.info("Abrindo stream para reprodução de áudio")
        stream_out = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True
        )
        
        # Reproduzir o áudio capturado
        logger.info("Reproduzindo áudio capturado...")
        print("🔊 Reproduzindo áudio capturado...")
        for frame in frames:
            stream_out.write(frame)
        
        # Fechar stream de saída
        stream_out.stop_stream()
        stream_out.close()
        
        # Finalizar PyAudio
        audio.terminate()
        
        logger.info("Teste de áudio concluído com sucesso!")
        print("✅ Teste concluído! Se você não ouviu o áudio, verifique sua configuração de áudio.")
    
    except Exception as e:
        logger.error(f"Erro durante o teste de áudio: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print("❌ Erro durante o teste de áudio. Verifique os logs para mais detalhes.")


if __name__ == "__main__":
    # Executar o teste de áudio
    asyncio.run(test_audio_capture_playback())
