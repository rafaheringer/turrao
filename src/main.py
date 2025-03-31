#!/usr/bin/env python3
"""
Turrão - Assistente Pessoal Conversacional
------------------------------------------

Versão com reprodução em tempo real que:
1. Detecta automaticamente quando o usuário começa a falar
2. Grava 5 segundos de áudio a partir desse momento
3. Envia o áudio para a API Realtime
4. Reproduz a resposta em tempo real enquanto a recebe
5. Permite múltiplas rodadas de conversa
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
    level=logging.WARNING,  # Reduzimos para WARNING para diminuir a verbosidade
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("main")

try:
    # Importação do agente realtime
    from src.api.realtime_agent import run_agent
    
    # Importar módulo de configuração
    from src.utils.config import load_config
    
    # Importar o detector de voz
    from src.audio.voice_detector import VoiceDetector
    from src.audio.smart_recorder import SmartRecorder
    
    # Carregar configurações
    config = load_config()
except ImportError as e:
    logger.critical(f"Erro ao importar módulos: {e}")
    logger.info("Certifique-se de que todas as dependências estão instaladas e que o ambiente virtual está ativado.")
    sys.exit(1)


async def main_async():
    """Função principal assíncrona que executa o assistente com reprodução em tempo real."""
    print("=== TURRÃO - ASSISTENTE PESSOAL - TEMPO REAL ===")
    print("Modo de conversa com detecção automática de voz!")
    print("Fale algo para iniciar uma conversa ou digite 'sair' e pressione Enter para encerrar.")
    
    # Manter o histórico de conversa (para futura implementação de contexto)
    conversation_history = []
    conversation_turn = 1
    
    # Sinalizadores e eventos para controle do fluxo
    exit_requested = False
    voice_detected_event = asyncio.Event()
    
    # Inicializar o SmartRecorder para o programa inteiro (para preservar calibração)
    print("Realizando calibração inicial do microfone (silêncio, por favor)...")
    global_recorder = SmartRecorder(sample_rate=16000)
    global_recorder.calibrate_microphone()  # Fazer calibração apenas uma vez
    print("Calibração concluída. Sistema pronto para conversas!")
    
    # Inicializar o detector de voz
    voice_detector = VoiceDetector()
    
    # Função de callback quando uma voz é detectada
    def on_voice_detected():
        voice_detected_event.set()
    
    # Iniciar o detector de voz
    voice_detector.start_monitoring(on_voice_detected)
    
    # Task para verificar entrada do teclado (para permitir sair do programa)
    async def check_keyboard_input():
        nonlocal exit_requested
        while not exit_requested:
            # Criar uma task para ler entrada não-bloqueante
            try:
                # Aguardar por entrada do teclado com timeout
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(None, lambda: input_with_timeout(0.5))
                
                if user_input and user_input.strip().lower() == 'sair':
                    print("Encerrando o Turrão. Até a próxima!")
                    exit_requested = True
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                pass  # Ignorar erros na entrada
            
            await asyncio.sleep(0.2)
    
    # Iniciar a task de verificação do teclado
    keyboard_task = asyncio.create_task(check_keyboard_input())
    
    try:
        while not exit_requested:
            print("\n" + "=" * 50)
            print(f"RODADA #{conversation_turn}")
            print("Aguardando você começar a falar... (diga algo ou digite 'sair' para encerrar)")
            
            # Limpar o evento de voz detectada
            voice_detected_event.clear()
            
            # Aguardar até que uma voz seja detectada ou o usuário solicite sair
            try:
                # Esperar até que uma voz seja detectada ou o programa seja encerrado
                await asyncio.wait_for(voice_detected_event.wait(), timeout=None)
                
                if exit_requested:
                    break
                
                # Se chegou aqui, uma voz foi detectada
                print(f"\nVoz detectada! Iniciando captura de fala (rodada #{conversation_turn})...")
                
                # Executar o agente com reprodução em tempo real, passando o gravador global calibrado
                resultado = await run_agent(global_recorder)
                
                if resultado:
                    # Adicionar à história da conversa (para futura implementação de contexto)
                    if 'text_response' in resultado and resultado['text_response']:
                        conversation_history.append({
                            'turn': conversation_turn,
                            'text_response': resultado['text_response']
                        })
                        print(f"\nResposta (texto): {resultado['text_response'][:200]}...")
                    else:
                        print("\nResposta em texto não disponível.")
                else:
                    print("\nA rodada falhou. Tente novamente.")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro durante a rodada #{conversation_turn}: {e}")
                logger.error(traceback.format_exc())
                print(f"\nErro na rodada #{conversation_turn}: {e}")
                print("Você pode tentar novamente na próxima rodada.")
            
            # Incrementar o contador de rodadas
            conversation_turn += 1
            
            # Pequena pausa entre rodadas
            await asyncio.sleep(1.0)
    
    finally:
        # Parar o detector de voz
        voice_detector.stop_monitoring()
        
        # Cancelar a task do teclado
        keyboard_task.cancel()
        try:
            await keyboard_task
        except asyncio.CancelledError:
            pass


def input_with_timeout(timeout=0.5):
    """Verifica se há entrada no stdin sem bloquear indefinidamente."""
    import select
    import sys
    
    # Verificar se há dados disponíveis para leitura
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    if r:
        return sys.stdin.readline().strip()
    return None


def main():
    """Função principal que inicia o assistente com reprodução em tempo real."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.")
    except Exception as e:
        logger.critical(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
