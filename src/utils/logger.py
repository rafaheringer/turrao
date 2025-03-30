"""
Configuração do sistema de logging para o assistente Turrão.

Este módulo implementa a configuração de logging formatado e colorido
para facilitar a depuração e o monitoramento da aplicação.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# Importação condicional para colorlog
try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False

# Variável global para armazenar a configuração
_config = None


def _get_config() -> Dict[str, Any]:
    """
    Obtém a configuração, carregando-a sob demanda.
    
    Este método carrega a configuração apenas quando necessário,
    evitando importação circular entre config.py e logger.py.
    
    Returns:
        Dicionário com a configuração carregada
    """
    global _config
    
    if _config is None:
        # Carregamento mínimo da configuração para evitar importação circular
        # Usamos os valores do ambiente ou padrões
        _config = {
            "logging": {
                "level": os.environ.get("LOG_LEVEL", "INFO").upper(),
                "file": os.environ.get("LOG_FILE", None)
            }
        }
        
        # Tentar importar a configuração completa se disponível
        try:
            # Importar apenas quando necessário para evitar círculos
            from src.utils.config import load_config
            _config = load_config()
        except (ImportError, Exception) as e:
            # Falha silenciosa, usaremos a configuração mínima
            pass
    
    return _config


def setup_logger(
    name: str = "turrão",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configura e retorna um logger formatado, opcionalmente com cores.
    
    Args:
        name: Nome do logger
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Caminho opcional para o arquivo de log
    
    Returns:
        Logger configurado
    """
    # Obter configuração
    config = _get_config()
    
    # Obter nível de log da configuração, parâmetro ou usar padrão
    if not log_level:
        # Verificar na configuração se existir a chave
        if "logging" in config and "level" in config["logging"]:
            log_level = config["logging"]["level"]
        else:
            # Fallback para variável de ambiente ou padrão
            log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # Obter arquivo de log da configuração ou parâmetro
    if not log_file and "logging" in config and "file" in config["logging"]:
        log_file = config["logging"]["file"]
    
    # Criar logger
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    # Remover handlers existentes para evitar duplicação
    if logger.handlers:
        logger.handlers.clear()
    
    # Formato do log
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Adicionar handler para console com cores se disponível
    if HAS_COLORLOG:
        # Configuração de cores para diferentes níveis de log
        color_formatter = colorlog.ColoredFormatter(
            "%(log_color)s" + log_format,
            datefmt=date_format,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            }
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(color_formatter)
    else:
        # Formatação padrão sem cores
        formatter = logging.Formatter(log_format, datefmt=date_format)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    # Adicionar handler para arquivo se especificado
    if log_file:
        # Criar diretório de logs se não existir
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "turrão") -> logging.Logger:
    """
    Obtém um logger existente ou cria um novo se não existir.
    
    Args:
        name: Nome do logger
    
    Returns:
        Logger para o nome especificado
    """
    logger = logging.getLogger(name)
    
    # Se o logger não tiver handlers, configurá-lo
    if not logger.handlers:
        return setup_logger(name)
    
    return logger
