"""
Cliente para comunicação com a API do OpenAI/ChatGPT.

Este módulo implementa a interação com a API do OpenAI para
processamento de linguagem natural e obtenção de respostas do modelo.
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Union

# Importação condicional para OpenAI SDK
try:
    import openai
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """
    Cliente para comunicação com a API do OpenAI.
    
    Implementa métodos para enviar mensagens ao ChatGPT e
    receber respostas, mantendo o histórico de conversação.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o cliente OpenAI com as configurações especificadas.
        
        Args:
            config: Dicionário com configurações para a API
            
        Raises:
            ImportError: Se o SDK do OpenAI não estiver instalado
            ValueError: Se a chave de API não estiver configurada
        """
        if not HAS_OPENAI:
            logger.critical("SDK do OpenAI não está instalado. A comunicação com a API não funcionará.")
            raise ImportError("SDK do OpenAI é necessário para comunicação com a API")
        
        self.config = config
        
        # Obter a chave de API
        self.api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.critical("Chave de API do OpenAI não configurada")
            raise ValueError("Chave de API do OpenAI é necessária. Configure via OPENAI_API_KEY ou no arquivo de configuração.")
        
        # Configurações do modelo
        self.model = config.get("model", "gpt-4o")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 1000)
        
        # Inicializar cliente assíncrono
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        logger.info(f"Cliente OpenAI inicializado com modelo {self.model}")
    
    async def send_message(self, 
                          message: str, 
                          conversation_history: Optional[List[Dict[str, str]]] = None,
                          system_prompt: Optional[str] = None) -> str:
        """
        Envia uma mensagem para o ChatGPT e recebe a resposta.
        
        Args:
            message: Mensagem do usuário para enviar ao modelo
            conversation_history: Histórico opcional de mensagens anteriores
            system_prompt: Prompt de sistema opcional para definir o comportamento do modelo
            
        Returns:
            Resposta do modelo como string
            
        Raises:
            RuntimeError: Se ocorrer erro durante a comunicação com a API
        """
        try:
            # Preparar as mensagens para a API
            messages = []
            
            # Adicionar prompt de sistema se fornecido
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Adicionar histórico de conversação se fornecido
            if conversation_history:
                messages.extend(conversation_history)
            
            # Adicionar a mensagem atual do usuário
            messages.append({"role": "user", "content": message})
            
            logger.debug(f"Enviando mensagem para o modelo {self.model}. Total de mensagens: {len(messages)}")
            
            # Chamar a API de forma assíncrona
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Extrair e retornar o texto da resposta
            assistant_response = response.choices[0].message.content.strip()
            logger.debug(f"Resposta recebida do modelo: {assistant_response[:50]}...")
            
            return assistant_response
            
        except openai.RateLimitError as e:
            logger.error(f"Erro de limite de taxa na API do OpenAI: {e}")
            return "Desculpe, estou recebendo muitas solicitações no momento. Poderia tentar novamente em alguns instantes?"
        
        except openai.APIError as e:
            logger.error(f"Erro na API do OpenAI: {e}")
            return "Desculpe, estou enfrentando problemas para acessar meu cérebro. Pode tentar novamente?"
        
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para o OpenAI: {e}")
            raise RuntimeError(f"Falha na comunicação com a API do OpenAI: {e}")
    
    async def stream_message(self, 
                           message: str, 
                           callback,
                           conversation_history: Optional[List[Dict[str, str]]] = None,
                           system_prompt: Optional[str] = None) -> str:
        """
        Envia uma mensagem ao ChatGPT e recebe a resposta em streaming.
        
        Args:
            message: Mensagem do usuário para enviar ao modelo
            callback: Função de callback que recebe fragmentos da resposta
            conversation_history: Histórico opcional de mensagens anteriores
            system_prompt: Prompt de sistema opcional para definir o comportamento do modelo
            
        Returns:
            Resposta completa do modelo como string
            
        Raises:
            RuntimeError: Se ocorrer erro durante a comunicação com a API
        """
        try:
            # Preparar as mensagens para a API
            messages = []
            
            # Adicionar prompt de sistema se fornecido
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Adicionar histórico de conversação se fornecido
            if conversation_history:
                messages.extend(conversation_history)
            
            # Adicionar a mensagem atual do usuário
            messages.append({"role": "user", "content": message})
            
            logger.debug(f"Iniciando streaming de mensagem para o modelo {self.model}")
            
            # Chamar a API em modo de streaming
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            
            # Processar a resposta em streaming
            full_response = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    
                    # Chamar o callback com o fragmento recebido
                    if callback:
                        await callback(content)
            
            logger.debug(f"Streaming concluído, resposta completa: {full_response[:50]}...")
            return full_response
            
        except Exception as e:
            logger.error(f"Erro ao fazer streaming de mensagem: {e}")
            raise RuntimeError(f"Falha no streaming da API do OpenAI: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Retorna informações sobre o modelo atual.
        
        Returns:
            Dicionário com informações do modelo
        """
        return {
            "name": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
