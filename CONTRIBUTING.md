# Guia de Contribuição

Obrigado pelo seu interesse em contribuir para o projeto Turrão! Este guia irá ajudá-lo a entender como você pode participar do desenvolvimento deste assistente pessoal conversacional.

## Código de Conduta

Ao participar deste projeto, você concorda em seguir nosso código de conduta, que inclui:

- Usar linguagem acolhedora e inclusiva
- Respeitar diferentes pontos de vista e experiências
- Aceitar críticas construtivas
- Focar no que é melhor para a comunidade
- Demonstrar empatia com outros membros da comunidade

## Como Contribuir

### Reportar Bugs

Encontrou um bug? Por favor, crie uma issue detalhando:

1. Título claro e descritivo
2. Passos para reproduzir o problema
3. Comportamento esperado vs. comportamento observado
4. Screenshots, se aplicável
5. Informações do ambiente (sistema operacional, versão do Python, etc.)

### Sugerir Melhorias

Tem uma ideia para melhorar o Turrão? Crie uma issue descrevendo:

1. Título claro e descritivo
2. Descrição detalhada da melhoria proposta
3. Benefícios e possíveis impactos da implementação
4. Exemplos de como a funcionalidade poderia ser usada

### Pull Requests

1. Bifurque (fork) o repositório
2. Crie um branch para sua feature (`git checkout -b feature/nome-da-feature`)
3. Implemente suas alterações
4. Adicione testes para suas alterações
5. Execute todos os testes e certifique-se de que passam
6. Atualize a documentação, se necessário
7. Faça commit de suas alterações (`git commit -m 'Adiciona nova feature'`)
8. Envie para o branch (`git push origin feature/nome-da-feature`)
9. Abra um Pull Request

## Diretrizes de Codificação

### Estilo de Código

Este projeto segue o estilo PEP 8 para Python. Alguns pontos importantes:

- Use 4 espaços para indentação (não tabs)
- Limite as linhas a 88 caracteres
- Use nomes descritivos para variáveis e funções
- Documente todas as funções e classes usando docstrings
- Adicione comentários explicativos quando necessário

### Testes

Todos os novos recursos devem incluir testes. Usamos pytest para testes unitários e de integração.

Para executar os testes:

```bash
python -m pytest
```

### Documentação

Atualize a documentação para qualquer alteração feita:

- Docstrings para funções e classes (seguindo o padrão NumPy/Google)
- README.md para alterações em funcionalidades principais
- Documentação em `/docs` para explicações mais detalhadas

## Estrutura do Projeto

Antes de contribuir, familiarize-se com a estrutura de diretórios:

```
/src
  /audio      - Módulos de captura e processamento de áudio
  /api        - Integrações com API do ChatGPT
  /core       - Lógica principal do assistente
  /utils      - Utilitários e ferramentas comuns
  /config     - Arquivos de configuração
/tests        - Testes unitários e de integração
/docs         - Documentação do projeto
/scripts      - Scripts de automação
```

## Processo de Release

1. Versões seguem o padrão [Semantic Versioning](https://semver.org/)
2. As releases são marcadas com tags no formato v1.0.0
3. Cada release tem notas detalhando as mudanças

## Perguntas?

Se você tiver dúvidas sobre como contribuir, sinta-se à vontade para abrir uma issue com sua pergunta.

Agradecemos seu interesse em melhorar o Turrão!
