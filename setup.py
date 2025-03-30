"""
Configuração do pacote para o assistente Turrão.

Este script configura o pacote para instalação via pip,
definindo metadados e dependências.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="turrão",
    version="0.1.0",
    author="Projeto Turrão",
    author_email="seu-email@exemplo.com",
    description="Assistente pessoal conversacional com personalidade forte",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/seu-usuario/turrão",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.12",
    install_requires=[
        "python-dotenv>=1.0.0",
        "PyAudio>=0.2.13",
        "SpeechRecognition>=3.10.0",
        "gTTS>=2.3.2",
        "pyttsx3>=2.90",
        "openai>=1.3.0",
        "numpy>=1.26.0",
        "colorlog>=6.7.0",
    ],
    entry_points={
        "console_scripts": [
            "turrão=src.main:main",
        ],
    },
)
