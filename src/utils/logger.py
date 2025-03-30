"""
Configuração do sistema de logging para o assistente Turrão.

Este módulo implementa a configuração de logging formatado e colorido
para facilitar a depuração e o monitoramento da aplicação.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

# Importação condicional para colorlog
try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False


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
    # Obter nível de log do ambiente ou usar padrão
    if not log_level:
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    
    numeric_level = getattr(logging, log_level, logging.INFO)
    
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
