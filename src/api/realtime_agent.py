"""
Cliente para comunicação com a API Realtime do OpenAI para agentes de voz.

Este módulo implementa a interação com a API Realtime da OpenAI,
permitindo conversação bidirecional de voz em tempo real.
"""

import asyncio
import base64
import os
import logging
import json
import threading
import time
from typing import Any, Callable, Dict, Optional
import numpy as np

from openai import AsyncOpenAI

from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)  # Aumentar o nível de log para DEBUG


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
        """
        self.config = config
        
        # Obter a chave de API
        self.api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.critical("Chave de API do OpenAI não configurada")
            raise ValueError("Chave de API do OpenAI é necessária. Configure via OPENAI_API_KEY ou no arquivo de configuração.")
        
        # Configurações do modelo e voz
        self.model = config.get("model") or os.environ.get("OPENAI_MODEL") or "gpt-4o-realtime-preview"
        self.voice = config.get("voice", "alloy")
        self.personality_prompt = config.get("personality_prompt", 
                                          "Você é o Turrão, um assistente com personalidade forte, irreverente e humor ácido. " +
                                          "Seja teimoso e responda com sarcasmo e ironia, mantendo um tom assertivo mas sempre com humor picante.")
        
        # Inicializar cliente assíncrono
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        # Configuração de áudio
        self.audio_format = config.get("audio_format", "pcm16")
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.output_channels = config.get("output_channels", 1)  # Canais para saída
        
        # Limites de detecção de voz
        self.voice_threshold = config.get("voice_threshold", 0.02)  # Limiar mais alto para evitar falsos positivos
        self.activation_frames = config.get("activation_frames", 5)  # Mais frames para confirmar voz
        self.noise_floor = config.get("noise_floor", 0.01)  # Nível de ruído de fundo a ser ignorado
        self.consecutive_voice_frames = 0  # Contador para frames consecutivos com voz
        
        # Estado interno
        self._is_listening = False
        self._is_speaking = False
        self._audio_buffer = bytearray()
        self._stop_event = threading.Event()
        self._connection = None
        self._calibrating = True  # Iniciar com calibração de ruído ambiente
        self._noise_calibration_samples = []
        self._calibration_frames = 20  # Número de frames para calibração
        
        logger.info(f"Agente Realtime inicializado com modelo {self.model} e voz {self.voice}")
    
    async def handle_message(self, message, audio_output_callback=None, text_callback=None):
        """
        Processa mensagens recebidas da API Realtime.
        
        Args:
            message: Mensagem recebida da API
            audio_output_callback: Função para processar áudio de saída
            text_callback: Função para processar texto de saída
        """
        event_type = message.get('type')
        logger.debug(f"Recebido evento: {event_type}")
        
        if event_type == "response.audio.delta" and 'delta' in message:
            # Processar delta de áudio
            audio_content = base64.b64decode(message['delta'])
            logger.debug(f"Recebido delta de áudio: {len(audio_content)} bytes")
            
            if audio_output_callback:
                # Adaptar o formato de áudio se necessário antes de enviar para callback
                processed_audio = self._process_output_audio(audio_content)
                await audio_output_callback(processed_audio)
        
        elif event_type == "response.text.delta" and 'delta' in message:
            # Processar delta de texto
            text = message['delta']
            logger.debug(f"Recebido delta de texto: {text}")
            
            if text_callback:
                await text_callback(text)
        
        elif event_type == "response.done":
            logger.info("Resposta concluída")
            self._is_speaking = False
            
        elif event_type == "input_audio_buffer.speech_started":
            logger.info("Detecção de fala: usuário começou a falar")
            
        elif event_type == "input_audio_buffer.speech_stopped":
            logger.info("Detecção de fala: usuário parou de falar")
    
    def _process_output_audio(self, audio_bytes):
        """
        Processa o áudio de saída para garantir compatibilidade com o sistema de reprodução.
        
        Args:
            audio_bytes: Bytes de áudio para processar
            
        Returns:
            bytes: Áudio processado pronto para reprodução
        """
        try:
            # Converter bytes para array numpy
            if self.audio_format == "pcm16":
                audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            else:
                audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
            
            # Verificar se precisamos adaptar os canais
            if self.output_channels > 1 and audio_array.ndim == 1:
                # Converter mono para estéreo/multicanal
                # Repetir o mesmo áudio em todos os canais
                audio_array = np.tile(audio_array.reshape(-1, 1), (1, self.output_channels))
                
                # Converter de volta para bytes
                if self.audio_format == "pcm16":
                    return audio_array.astype(np.int16).tobytes()
                else:
                    return audio_array.astype(np.float32).tobytes()
            
            # Se não precisar adaptar, retornar o áudio original
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Erro ao processar áudio de saída: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return audio_bytes  # Em caso de erro, retorna o áudio original
    
    async def detect_voice(self, audio_chunk):
        """
        Detecta se há voz no áudio.
        
        Args:
            audio_chunk: Bytes de áudio para analisar
            
        Returns:
            bool: True se voz foi detectada, False caso contrário
        """
        try:
            if not audio_chunk or len(audio_chunk) < 2:
                return False
            
            # Determinamos o formato com base no tipo de áudio configurado
            dtype = np.int16 if self.audio_format == "pcm16" else np.float32
            
            # Converter para array numpy para análise
            audio_array = np.frombuffer(audio_chunk, dtype=dtype)
            
            # Normalizar para float para cálculo de RMS se for int16
            if dtype == np.int16:
                float_array = audio_array.astype(np.float32) / 32768.0
                rms = np.sqrt(np.mean(np.square(float_array)))
            else:
                rms = np.sqrt(np.mean(np.square(audio_array)))
            
            # Calibração de ruído de fundo - ajusta automaticamente o threshold
            if self._calibrating:
                self._noise_calibration_samples.append(rms)
                
                if len(self._noise_calibration_samples) >= self._calibration_frames:
                    # Calcular estatísticas do ruído de fundo
                    noise_mean = np.mean(self._noise_calibration_samples)
                    noise_std = np.std(self._noise_calibration_samples)
                    
                    # Ajustar o threshold baseado no ruído ambiente (média + 3*desvio padrão)
                    adjusted_threshold = noise_mean + 3 * noise_std
                    
                    # Não deixar o threshold ser menor que o mínimo configurado
                    self.noise_floor = max(noise_mean, self.noise_floor)
                    self.voice_threshold = max(adjusted_threshold, self.voice_threshold)
                    
                    logger.info(f"Calibração concluída. Ruído ambiente: {noise_mean:.6f} ± {noise_std:.6f}")
                    logger.info(f"Threshold ajustado: {self.voice_threshold:.6f}")
                    
                    self._calibrating = False
                
                return False  # Não detectar voz durante calibração
            
            # Verificar se o áudio tem amplitude suficiente para ser considerado voz
            has_signal = rms > self.noise_floor
            has_voice = rms > self.voice_threshold
            
            if has_voice:
                self.consecutive_voice_frames += 1
                if self.consecutive_voice_frames >= 2:  # Exigir pelo menos 2 frames consecutivos para log
                    logger.debug(f"Voz detectada! RMS={rms:.6f}, threshold={self.voice_threshold}")
            else:
                self.consecutive_voice_frames = 0
                
                # Mostrar log para sinais acima do ruído mas abaixo do threshold
                if has_signal and not has_voice:
                    logger.debug(f"Sinal detectado, mas abaixo do threshold. RMS={rms:.6f}")
            
            # Retornar true apenas quando tiver confirmação de voz
            return has_voice
            
        except Exception as e:
            logger.error(f"Erro ao detectar voz: {e}")
            return False
    
    async def send_audio(self, connection, audio_chunk):
        """
        Envia um chunk de áudio para a API Realtime.
        
        Args:
            connection: Conexão WebSocket com a API
            audio_chunk: Bytes de áudio para enviar
        """
        try:
            if not connection or not audio_chunk or len(audio_chunk) < 2:
                return
            
            # Codificar o áudio em Base64
            base64_audio = base64.b64encode(audio_chunk).decode('ascii')
            
            # Enviar para a API
            await connection.send({
                "type": "input_audio_buffer.append",
                "audio": base64_audio
            })
            
            # Atualizar buffer para enviar acumulado
            self._audio_buffer.extend(audio_chunk)
            
            logger.debug(f"Enviado chunk de áudio: {len(audio_chunk)} bytes")
            
        except Exception as e:
            logger.error(f"Erro ao enviar áudio: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def process_audio_stream(self, connection, audio_input_stream):
        """
        Processa continuamente o stream de áudio, detectando voz e enviando para a API.
        
        Args:
            connection: Conexão WebSocket com a API
            audio_input_stream: Stream de áudio do microfone
        """
        self._is_listening = True
        activation_counter = 0
        chunk_counter = 0
        
        logger.info("Iniciando monitoramento de áudio do microfone")
        logger.info("Calibrando níveis de ruído ambiente... aguarde")
        
        # Inicialmente não enviamos nada, apenas monitoramos a ativação por voz
        while self._is_listening and not self._stop_event.is_set():
            try:
                # Ler dados do stream de áudio (chunks menores para detecção mais rápida)
                audio_chunk = await audio_input_stream.read(1024)
                
                # Detectar voz no áudio
                has_voice = await self.detect_voice(audio_chunk)
                
                # Se detectou voz, incrementa contador de ativação
                if has_voice:
                    activation_counter += 1
                    if activation_counter == 2:  # Reduzimos o log para não poluir tanto
                        logger.info("Possível voz detectada, monitorando...")
                    
                    # Enviar o áudio assim que detectar voz
                    await self.send_audio(connection, audio_chunk)
                    
                    # Se atingir o limite de frames com voz, solicita resposta
                    if activation_counter >= self.activation_frames and not self._is_speaking:
                        logger.info(f"Voz confirmada após {activation_counter} frames! Enviando áudio para a API")
                        self._is_speaking = True
                        
                        # Solicitar resposta da API (não fazemos commit porque queremos manter o stream aberto)
                        await connection.send({"type": "response.create"})
                else:
                    # Enviar áudio mesmo sem voz, se estiver em uma conversa ativa
                    if self._is_speaking:
                        await self.send_audio(connection, audio_chunk)
                    
                    # Resetar contador de ativação gradualmente
                    if activation_counter > 0:
                        activation_counter -= 0.2  # Decrementar gradualmente para evitar cortes em pausas curtas
                
                # Contador de chunks processados (para debug)
                chunk_counter += 1
                if chunk_counter % 200 == 0:  # Reduzido a frequência para não logar tanto
                    logger.debug(f"Processados {chunk_counter} chunks de áudio")
                
                # Pausa curta para não sobrecarregar
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Erro ao processar áudio de entrada: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(0.1)  # Pausa mais longa em caso de erro
    
    async def start_conversation(self,
                               audio_input_stream,
                               audio_output_stream=None,
                               on_speech_recognized=None,
                               on_response_started=None,
                               on_response_text=None,
                               on_completion=None):
        """
        Inicia uma conversa com a API Realtime.
        
        Args:
            audio_input_stream: Stream de áudio do microfone
            audio_output_stream: Stream de áudio de saída (opcional)
            on_speech_recognized: Callback quando a fala é reconhecida
            on_response_started: Callback quando a resposta começa
            on_response_text: Callback para cada trecho de texto da resposta
            on_completion: Callback quando a conversação é concluída
        """
        self._stop_event.clear()
        
        # Definir callbacks locais
        async def text_callback(text):
            if on_response_text:
                await asyncio.to_thread(on_response_text, text)
        
        async def audio_callback(audio_data):
            try:
                if audio_output_stream:
                    await audio_output_stream.write(audio_data)
            except Exception as e:
                logger.error(f"Erro ao reproduzir áudio: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        try:
            # Conectar à API Realtime
            logger.info(f"Conectando à API Realtime com modelo {self.model}")
            
            async with self.client.beta.realtime.connect(model=self.model) as connection:
                self._connection = connection
                logger.info("Conexão estabelecida!")
                
                # Notificar início da sessão
                if on_response_started:
                    await asyncio.to_thread(on_response_started)
                
                # Configurar a sessão
                await connection.session.update(session={
                    'modalities': ['audio', 'text'],
                    'instructions': self.personality_prompt,
                    'voice': self.voice,
                    'output_audio_format': self.audio_format,
                    'turn_detection': {
                        'type': 'server_vad',
                        'silence_duration_ms': 1000,  # 1 segundo de silêncio
                        'interrupt_response': True
                    }
                })
                logger.info("Sessão configurada")
                
                # Iniciar task para processar o áudio
                processing_task = asyncio.create_task(
                    self.process_audio_stream(connection, audio_input_stream)
                )
                
                # Processar eventos de resposta
                try:
                    async for event in connection:
                        # Convertendo o evento para dicionário para processamento
                        event_dict = {}
                        for attr in dir(event):
                            if not attr.startswith('_') and not callable(getattr(event, attr)):
                                try:
                                    event_dict[attr] = getattr(event, attr)
                                except:
                                    pass
                        
                        # Reconhecimento de fala
                        if event_dict.get('type') == "voice_to_text.message.content" and on_speech_recognized:
                            if hasattr(event, 'content') and hasattr(event.content, 'text'):
                                text = event.content.text
                                await asyncio.to_thread(on_speech_recognized, text)
                                logger.info(f"Fala reconhecida: {text}")
                        
                        # Processar o evento para áudio e texto
                        await self.handle_message(
                            event_dict, 
                            audio_output_callback=audio_callback,
                            text_callback=text_callback
                        )
                        
                        # Verificar se devemos parar
                        if self._stop_event.is_set():
                            break
                            
                except Exception as e:
                    logger.error(f"Erro ao processar eventos: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                finally:
                    # Cancelar a task de processamento
                    if not processing_task.done():
                        processing_task.cancel()
                        try:
                            await processing_task
                        except asyncio.CancelledError:
                            pass
        
        except Exception as e:
            logger.error(f"Erro na conversação: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            self._connection = None
            self._stop_event.set()
            self._is_speaking = False
            # Executar callback de conclusão
            if on_completion:
                await asyncio.to_thread(on_completion)
    
    def stop_listening(self):
        """Interrompe a captura de áudio."""
        self._is_listening = False
    
    def stop(self):
        """Interrompe a conversação."""
        self._stop_event.set()
        self.stop_listening()
        logger.info("Conversação interrompida")
    
    def set_personality(self, personality_prompt: str) -> None:
        """
        Define ou atualiza a personalidade do agente.
        
        Args:
            personality_prompt: Prompt de sistema que define a personalidade
        """
        self.personality_prompt = personality_prompt
        logger.debug(f"Personalidade do agente atualizada: {personality_prompt[:50]}...")