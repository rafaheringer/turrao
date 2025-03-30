#!/usr/bin/env python3
"""
Turrão - Assistente Pessoal Conversacional
------------------------------------------

Versão simplificada para teste que:
1. Dá 5 segundos para o usuário falar
2. Envia o áudio para a API Realtime
3. Reproduz a resposta
"""

import asyncio
import logging
import os
import sys
import traceback

# Adicionar o diretório raiz ao Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configuração básica de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("main")

try:
    # Importação simplificada - apenas o agente realtime
    from src.api.realtime_agent import run_agent
except ImportError as e:
    logger.critical(f"Erro ao importar módulos: {e}")
    logger.info("Certifique-se de que todas as dependências estão instaladas e que o ambiente virtual está ativado.")
    sys.exit(1)


async def main_async():
    """Função principal assíncrona que executa o teste simplificado."""
    print("=== TURRÃO - ASSISTENTE PESSOAL - TESTE SIMPLIFICADO ===")
    print("Você terá 5 segundos para falar após pressionar Enter.")
    print("Pressione Enter para iniciar...")
    input()  # Aguardar entrada do usuário
    
    try:
        # Executar o agente simplificado
        resultado = await run_agent()
        
        if resultado:
            print("\nTeste concluído com sucesso!")
            print(f"Texto da resposta: {resultado['text_response'][:100]}...")
        else:
            print("\nO teste falhou. Verifique os logs para mais detalhes.")
    
    except Exception as e:
        logger.error(f"Erro durante a execução: {e}")
        logger.error(traceback.format_exc())
        print(f"\nErro: {e}")


def main():
    """Função principal que inicia o assistente em modo simplificado."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.")
    except Exception as e:
        logger.critical(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
