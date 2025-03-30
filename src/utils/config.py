"""
Módulo de configuração para o assistente Turrão.

Este módulo é responsável por carregar e validar as configurações da aplicação
a partir de arquivos de configuração e variáveis de ambiente.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Importação condicional para python-dotenv
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Carrega configurações de arquivos e variáveis de ambiente.
    
    Args:
        config_path: Caminho opcional para arquivo de configuração JSON
        
    Returns:
        Dicionário com as configurações carregadas
    """
    # Configurações padrão
    config = {
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "format": "Int16",
            "chunk_size": 1024,
        },
        "stt": {
            "model": "default",
            "language": "pt-BR"
        },
        "tts": {
            "provider": "gTTS",
            "voice": "pt-BR",
            "rate": 1.0,
        },
        "api": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.7,
        },
        "assistant": {
            "name": "Turrão",
            "personality": (
                "Você é o Turrão, um assistente pessoal com personalidade forte, "
                "irreverente e um humor ácido. Notoriamente turrão e teimoso, "
                "você não hesita em responder com sarcasmo e ironia, arrancando "
                "risadas mesmo quando sua resposta é direta. Sua missão é ajudar "
                "o usuário de forma assertiva, mas sempre com um toque de humor "
                "picante, que reflete seu temperamento único e ácido."
            ),
            "max_history": 10
        }
    }
    
    # Carregar variáveis de ambiente
    _load_environment_variables()
    
    # Sobrescrever com configurações do arquivo JSON
    if config_path:
        _load_config_file(config_path, config)
    
    # Sobrescrever com variáveis de ambiente
    _override_with_env_vars(config)
    
    logger.debug(f"Configuração carregada: {json.dumps(config, indent=2)}")
    return config


def _load_environment_variables() -> None:
    """Carrega variáveis de ambiente do arquivo .env se disponível."""
    if not HAS_DOTENV:
        logger.warning("python-dotenv não está instalado. Variáveis de .env não serão carregadas.")
        return
    
    # Procurar pelo arquivo .env no diretório atual e acima
    dot_env = Path(".env")
    if not dot_env.exists():
        # Tentar encontrar .env no diretório raiz do projeto
        project_root = Path(__file__).parents[2]  # src/utils/ -> src/ -> root/
        dot_env = project_root / ".env"
    
    if dot_env.exists():
        logger.debug(f"Carregando variáveis de ambiente de {dot_env}")
        load_dotenv(dotenv_path=dot_env)
    else:
        logger.warning("Arquivo .env não encontrado")


def _load_config_file(config_path: str, config: Dict[str, Any]) -> None:
    """
    Carrega configurações de um arquivo JSON.
    
    Args:
        config_path: Caminho para o arquivo de configuração
        config: Dicionário de configurações a ser atualizado
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            file_config = json.load(f)
            
        # Atualizar configuração de forma recursiva
        _recursive_update(config, file_config)
        logger.debug(f"Configurações carregadas de {config_path}")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Erro ao carregar arquivo de configuração {config_path}: {e}")


def _override_with_env_vars(config: Dict[str, Any]) -> None:
    """
    Sobrescreve configurações com variáveis de ambiente.
    
    Args:
        config: Dicionário de configurações a ser atualizado
    """
    # Mapeamento de variáveis de ambiente para chaves de configuração
    env_mappings = {
        # Áudio
        "AUDIO_SAMPLE_RATE": ("audio", "sample_rate", int),
        "AUDIO_CHANNELS": ("audio", "channels", int),
        "AUDIO_FORMAT": ("audio", "format", str),
        "AUDIO_CHUNK_SIZE": ("audio", "chunk_size", int),

        # API
        "OPENAI_API_KEY": ("api", "api_key", str),
        "OPENAI_MODEL": ("api", "model", str),
        "API_TEMPERATURE": ("api", "temperature", float),
        "OPENAI_VOICE": ("api", "voice", str),
        
        # Assistente
        "ASSISTANT_NAME": ("assistant", "name", str),
        "ASSISTANT_MAX_HISTORY": ("assistant", "max_history", int),
    }
    
    for env_var, (section, key, type_func) in env_mappings.items():
        if env_var in os.environ:
            try:
                value = os.environ[env_var]
                # Converter para o tipo adequado
                if type_func == bool:
                    # Tratamento especial para booleanos
                    value = value.lower() in ("true", "yes", "1", "t", "y")
                else:
                    value = type_func(value)
                
                # Atualizar a configuração
                config[section][key] = value
                
                # Log especial para chaves de API (não mostrar o valor completo)
                if "api_key" in key:
                    logger.debug(f"Variável de ambiente {env_var} definida: ***")
                else:
                    logger.debug(f"Variável de ambiente {env_var} definida: {value}")
            except (ValueError, KeyError) as e:
                logger.warning(f"Erro ao processar variável de ambiente {env_var}: {e}")


def _recursive_update(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """
    Atualiza recursivamente um dicionário com valores de outro.
    
    Args:
        target: Dicionário alvo a ser atualizado
        source: Dicionário fonte com os valores a serem copiados
    """
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _recursive_update(target[key], value)
        else:
            target[key] = value
