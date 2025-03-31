"""
Configurações específicas para execução no Raspberry Pi.

Este módulo contém configurações e ajustes específicos para o ambiente
do Raspberry Pi, incluindo configurações de hardware e otimizações.
"""

import os
from typing import Dict, Any


def get_raspberry_pi_config() -> Dict[str, Any]:
    """
    Retorna configurações otimizadas para o Raspberry Pi.
    
    Returns:
        Dicionário com configurações para o Raspberry Pi
    """
    config = {
        "system": {
            # Configurações específicas de hardware
            "cpu_limit": 80,  # Limite de uso de CPU em porcentagem
            "memory_limit": 500,  # Limite de uso de memória em MB
            "temperature_warning": 70,  # Temperatura em °C para aviso
            "temperature_critical": 80,  # Temperatura em °C para desligar
            # Configurações de energia
            "power_save_mode": True,
            "disable_hdmi": True,  # Desativar HDMI para economizar energia
            "disable_led": True,  # Desativar LEDs para economizar energia
        },
        "gpio": {
            # Configuração para LEDs de status
            "status_led_pin": 17,  # LED de status geral
            "listening_led_pin": 27,  # LED para indicar que está ouvindo
            "speaking_led_pin": 22,  # LED para indicar que está falando
            # Configuração para botão físico
            "button_pin": 4,  # Botão para ativar manualmente o assistente
            "button_hold_time": 0.5,  # Tempo em segundos para segurar o botão
        }
    }
    
    return config


def setup_raspberry_pi() -> None:
    """
    Configura o Raspberry Pi para execução otimizada do assistente.
    
    Esta função realiza ajustes no sistema operacional para otimizar
    o desempenho e reduzir o consumo de energia.
    """
    try:
        # Estas operações só funcionarão no Raspberry Pi e exigem permissões de superusuário
        # Verificar se estamos em um Raspberry Pi
        if not os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
            print("Não parece ser um Raspberry Pi. Pulando otimizações de sistema.")
            return
            
        config = get_raspberry_pi_config()
        
        # Aplicar configurações de economia de energia
        if config["system"]["power_save_mode"]:
            # Desativar HDMI para economizar energia
            if config["system"]["disable_hdmi"]:
                os.system("tvservice -o")
                
            # Desativar LEDs para economizar energia
            if config["system"]["disable_led"]:
                with open('/sys/class/leds/led0/brightness', 'w') as f:
                    f.write('0')
                with open('/sys/class/leds/led1/brightness', 'w') as f:
                    f.write('0')
        
        print("Raspberry Pi configurado com otimizações de sistema.")
    except Exception as e:
        print(f"Erro ao configurar o Raspberry Pi: {e}")
        print("Continuando sem otimizações de sistema.")


def get_cpu_temperature() -> float:
    """
    Obtém a temperatura atual da CPU do Raspberry Pi.
    
    Returns:
        Temperatura em graus Celsius
    """
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
        return temp
    except:
        return 0.0


def monitor_system_resources() -> Dict[str, Any]:
    """
    Monitora recursos do sistema no Raspberry Pi.
    
    Returns:
        Dicionário com informações de recursos do sistema
    """
    result = {
        "temperature": 0.0,
        "cpu_usage": 0.0,
        "memory_usage": 0.0,
        "disk_usage": 0.0
    }
    
    try:
        # Temperatura
        result["temperature"] = get_cpu_temperature()
        
        # Uso de CPU
        with open('/proc/stat', 'r') as f:
            cpu = f.readline().split()
        total = float(sum(float(i) for i in cpu[1:]))
        idle = float(cpu[4])
        result["cpu_usage"] = 100.0 * (1.0 - idle / total)
        
        # Uso de memória
        with open('/proc/meminfo', 'r') as f:
            mem_info = {}
            for line in f:
                key, value = line.split(':')
                mem_info[key.strip()] = int(value.split()[0])
        total_mem = mem_info['MemTotal']
        free_mem = mem_info['MemFree']
        buffers = mem_info.get('Buffers', 0)
        cached = mem_info.get('Cached', 0)
        used_mem = total_mem - free_mem - buffers - cached
        result["memory_usage"] = 100.0 * used_mem / total_mem
        
        # Uso de disco
        disk_info = os.statvfs('/')
        total_disk = disk_info.f_blocks * disk_info.f_frsize
        free_disk = disk_info.f_bfree * disk_info.f_frsize
        result["disk_usage"] = 100.0 * (1.0 - float(free_disk) / total_disk)
        
    except Exception as e:
        print(f"Erro ao monitorar recursos do sistema: {e}")
    
    return result
