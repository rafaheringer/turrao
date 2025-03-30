"""
Gerenciador de conversação para o assistente Turrão.

Este módulo implementa a lógica de gerenciamento de conversação,
mantendo o histórico, aplicando a personalidade e coordenando a interação
com a API do ChatGPT.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.api.openai_client import OpenAIClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """
    Gerenciador de conversação do assistente Turrão.
    
    Responsável por manter o contexto da conversa, gerenciar o histórico
    e aplicar a personalidade do assistente nas interações.
    """
    
    def __init__(self, openai_client: OpenAIClient, config: Dict[str, Any]):
        """
        Inicializa o gerenciador de conversação.
        
        Args:
            openai_client: Cliente para comunicação com a API do OpenAI
            config: Configurações do assistente
        """
        self.openai_client = openai_client
        self.config = config
        
        # Configurações de personalidade
        self.assistant_name = config.get("name", "Turrão")
        self.personality = config.get("personality", "")
        self.max_history = config.get("max_history", 10)
        
        # Histórico de conversação
        self.conversation_history: List[Dict[str, str]] = []
        
        # Sessão atual
        self.session_start_time = datetime.now()
        self.session_id = f"session_{self.session_start_time.strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Gerenciador de conversação inicializado para o assistente {self.assistant_name}")
    
    def _create_system_prompt(self) -> str:
        """
        Cria o prompt de sistema que define a personalidade do assistente.
        
        Returns:
            Prompt de sistema formatado
        """
        # Prompt base com a personalidade do Turrão
        system_prompt = self.personality
        
        # Adicionar informações de contexto
        system_prompt += f"\n\nHoje é {datetime.now().strftime('%d/%m/%Y')} e são aproximadamente {datetime.now().strftime('%H:%M')}."
        
        # Adicionar regras específicas
        system_prompt += """
        
        Regras de comportamento:
        1. Mantenha seu tom teimoso, irreverente e com humor ácido em todas as respostas
        2. Seja direto e objetivo, mas nunca perca a oportunidade de inserir uma piada ou comentário sarcástico
        3. Quando não souber uma resposta, admita com sinceridade, mas mantenha seu estilo único
        4. Evite respostas genéricas que poderiam vir de qualquer assistente
        5. Use gírias brasileiras ocasionalmente para dar mais personalidade às respostas
        """
        
        return system_prompt
    
    async def process_input(self, user_input: str) -> str:
        """
        Processa a entrada do usuário e gera uma resposta.
        
        Args:
            user_input: Texto de entrada do usuário
            
        Returns:
            Resposta do assistente
        """
        try:
            # Adicionar a mensagem do usuário ao histórico
            self.conversation_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Manter o histórico dentro do limite configurado
            if len(self.conversation_history) > self.max_history * 2:  # multiplicado por 2 para contar pares de perguntas/respostas
                # Remover as mensagens mais antigas, mantendo a estrutura de pares
                self.conversation_history = self.conversation_history[-self.max_history * 2:]
            
            # Criar o prompt de sistema
            system_prompt = self._create_system_prompt()
            
            # Obter resposta do modelo
            response = await self.openai_client.send_message(
                message=user_input,
                conversation_history=self.conversation_history,
                system_prompt=system_prompt
            )
            
            # Adicionar a resposta ao histórico
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Erro ao processar entrada do usuário: {e}")
            # Resposta de fallback em caso de erro
            fallback_response = (
                f"Olha, eu queria muito te responder, mas estou tendo um probleminha técnico aqui. "
                f"Você sabe como é, né? Até as máquinas têm seus dias ruins... "
                f"Pode tentar de novo? Prometo que vou tentar ser menos teimoso dessa vez."
            )
            return fallback_response
    
    async def process_input_streaming(self, user_input: str, callback) -> str:
        """
        Processa a entrada do usuário e gera uma resposta em streaming.
        
        Args:
            user_input: Texto de entrada do usuário
            callback: Função a ser chamada com fragmentos da resposta
            
        Returns:
            Resposta completa do assistente
        """
        try:
            # Adicionar a mensagem do usuário ao histórico
            self.conversation_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Manter o histórico dentro do limite configurado
            if len(self.conversation_history) > self.max_history * 2:
                self.conversation_history = self.conversation_history[-self.max_history * 2:]
            
            # Criar o prompt de sistema
            system_prompt = self._create_system_prompt()
            
            # Obter resposta do modelo em streaming
            response = await self.openai_client.stream_message(
                message=user_input,
                callback=callback,
                conversation_history=self.conversation_history,
                system_prompt=system_prompt
            )
            
            # Adicionar a resposta ao histórico
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Erro ao processar entrada do usuário em streaming: {e}")
            fallback_response = (
                f"Eita, parece que deu um probleminha aqui. "
                f"Tá difícil conversar hoje, hein? Vamos tentar de novo?"
            )
            return fallback_response
    
    def clear_history(self) -> None:
        """Limpa o histórico de conversação atual."""
        self.conversation_history = []
        logger.info("Histórico de conversação limpo")
    
    def save_conversation(self, file_path: Optional[str] = None) -> str:
        """
        Salva a conversa atual em um arquivo JSON.
        
        Args:
            file_path: Caminho opcional para salvar o arquivo
            
        Returns:
            Caminho do arquivo salvo
        """
        if not file_path:
            # Criar diretório para logs de conversas se não existir
            logs_dir = os.path.join(os.getcwd(), "logs", "conversations")
            os.makedirs(logs_dir, exist_ok=True)
            
            # Gerar nome de arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(logs_dir, f"conversation_{timestamp}.json")
        
        # Preparar dados para salvar
        conversation_data = {
            "assistant": self.assistant_name,
            "session_id": self.session_id,
            "start_time": self.session_start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "messages": self.conversation_history
        }
        
        # Salvar em formato JSON
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(conversation_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Conversa salva em {file_path}")
        return file_path
    
    def load_conversation(self, file_path: str) -> None:
        """
        Carrega uma conversa de um arquivo JSON.
        
        Args:
            file_path: Caminho do arquivo a ser carregado
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                conversation_data = json.load(f)
            
            # Verificar se o formato é válido
            if "messages" in conversation_data and isinstance(conversation_data["messages"], list):
                self.conversation_history = conversation_data["messages"]
                logger.info(f"Conversa carregada de {file_path}")
            else:
                logger.error(f"Formato de arquivo inválido: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao carregar conversa de {file_path}: {e}")
            raise
