#!/usr/bin/env python3
"""
Script de configuração do ambiente para o assistente Turrão.

Este script automatiza a preparação do ambiente de desenvolvimento,
criando o ambiente virtual, instalando dependências e configurando
os arquivos necessários.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def print_header(message):
    """Imprime uma mensagem formatada como cabeçalho."""
    print("\n" + "=" * 60)
    print(f" {message}")
    print("=" * 60 + "\n")


def print_step(message):
    """Imprime uma mensagem formatada como passo."""
    print(f"\n> {message}")


def run_command(command, cwd=None):
    """
    Executa um comando no shell e retorna o resultado.
    
    Args:
        command: Comando a ser executado
        cwd: Diretório de trabalho opcional
        
    Returns:
        True se o comando for bem-sucedido, False caso contrário
    """
    try:
        subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar comando: {command}")
        print(f"Saída de erro: {e.stderr}")
        return False


def create_env_file():
    """Cria o arquivo .env a partir do .env.example se não existir."""
    env_example_path = Path(".env.example")
    env_path = Path(".env")
    
    if not env_path.exists() and env_example_path.exists():
        print_step("Criando arquivo .env a partir do .env.example")
        shutil.copy(env_example_path, env_path)
        print("Arquivo .env criado com sucesso!")
        print("IMPORTANTE: Edite o arquivo .env para adicionar sua chave de API do OpenAI.")
    elif env_path.exists():
        print("Arquivo .env já existe.")
    else:
        print("ERRO: Arquivo .env.example não encontrado!")


def main():
    """Função principal do script de configuração."""
    print_header("Configuração do Ambiente para o Assistente Turrão")
    
    # Verificar a versão do Python
    python_version = platform.python_version()
    print(f"Versão do Python: {python_version}")
    
    major, minor, _ = map(int, python_version.split("."))
    if major < 3 or (major == 3 and minor < 12):
        print("AVISO: Este projeto foi desenvolvido para Python 3.12+.")
        proceed = input("Deseja continuar mesmo assim? (s/n): ").lower()
        if proceed != "s":
            print("Configuração cancelada.")
            return
    
    # Detectar sistema operacional
    system = platform.system()
    print(f"Sistema Operacional: {system}")
    
    # Definir o comando para o ambiente virtual
    venv_dir = ".venv"
    if system == "Windows":
        python_cmd = "python"
        pip_cmd = f"{venv_dir}\\Scripts\\pip"
        activate_cmd = f"{venv_dir}\\Scripts\\activate"
    else:
        python_cmd = "python3"
        pip_cmd = f"{venv_dir}/bin/pip"
        activate_cmd = f"source {venv_dir}/bin/activate"
    
    # Verificar se o ambiente virtual já existe
    if os.path.exists(venv_dir):
        print(f"Ambiente virtual '{venv_dir}' já existe.")
        recreate = input("Deseja recriá-lo? (s/n): ").lower()
        if recreate == "s":
            print_step("Removendo ambiente virtual existente")
            if system == "Windows":
                run_command(f"rmdir /S /Q {venv_dir}")
            else:
                run_command(f"rm -rf {venv_dir}")
        else:
            print("Usando ambiente virtual existente.")
    
    # Criar ambiente virtual se necessário
    if not os.path.exists(venv_dir):
        print_step("Criando ambiente virtual")
        if not run_command(f"{python_cmd} -m venv {venv_dir}"):
            print("Falha ao criar ambiente virtual. Encerrando.")
            return
    
    # Atualizar pip
    print_step("Atualizando pip")
    run_command(f"{pip_cmd} install --upgrade pip")
    
    # Instalar dependências
    print_step("Instalando dependências")
    if run_command(f"{pip_cmd} install -r requirements.txt"):
        print("Dependências instaladas com sucesso!")
    else:
        print("AVISO: Falha ao instalar algumas dependências.")
    
    # Criar arquivo .env
    create_env_file()
    
    # Instruções finais
    print_header("Configuração Concluída")
    print(f"Para ativar o ambiente virtual, execute:\n  {activate_cmd}")
    print("\nPara iniciar o assistente:")
    print("  python -m src.main")
    print("\nAntes de iniciar, verifique se:")
    print("1. Você configurou sua chave de API do OpenAI no arquivo .env")
    print("2. Seu microfone e alto-falantes estão funcionando corretamente")
    print("\nEm caso de problemas com dependências de áudio:")
    if system == "Windows":
        print("- Para PyAudio no Windows, pode ser necessário instalar manualmente")
        print("  Baixe o arquivo .whl adequado de: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")
    elif system == "Linux":
        print("- Para PyAudio no Linux, pode ser necessário instalar dependências do sistema:")
        print("  sudo apt-get install portaudio19-dev python3-dev")
    elif system == "Darwin":  # macOS
        print("- Para PyAudio no macOS, pode ser necessário instalar dependências do sistema:")
        print("  brew install portaudio")
    
    print("\nDivirta-se conversando com o Turrão! 😎")


if __name__ == "__main__":
    main()
