# Gerenciador de Certificados Digitais

Esta é uma aplicação para gerenciar certificados digitais de clientes, permitindo o cadastro e acompanhamento das datas de vencimento.

## Funcionalidades

- Cadastro de clientes com Razão Social, CNPJ e Data de Vencimento do Certificado
- Visualização de todos os clientes cadastrados
- Status automático dos certificados:
  - REGULAR: mais de 30 dias para vencer
  - PRÓXIMO AO VENCIMENTO: 30 dias ou menos para vencer
  - VENCIDO: certificado já vencido
- Exclusão de clientes
- Interface gráfica intuitiva

## Requisitos para Desenvolvimento

- Python 3.6 ou superior
- Bibliotecas Python listadas em `requirements.txt`

## Instalação para Desenvolvimento

1. Clone este repositório
2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Como Usar Durante Desenvolvimento

1. Execute o arquivo `app.py`:
```bash
python app.py
```

2. Na interface da aplicação:
   - Preencha os campos Razão Social, CNPJ e Data de Vencimento
   - Clique em "Cadastrar" para adicionar um novo cliente
   - A lista de clientes será atualizada automaticamente
   - Use o botão "Atualizar Lista" para forçar uma atualização
   - Selecione um cliente e clique em "Excluir Selecionado" para removê-lo

## Criar Executável

Para criar um executável que pode ser instalado em qualquer computador Windows:

1. Instale as dependências (se ainda não instalou):
```bash
pip install -r requirements.txt
```

2. Execute o script de build:
```bash
python build.py
```

3. O executável será criado na pasta `dist` com o nome "Gerenciador de Certificados.exe"

## Usando o Executável

1. Copie o arquivo "Gerenciador de Certificados.exe" da pasta `dist` para o computador desejado
2. Dê dois cliques no executável para iniciar a aplicação
3. Na primeira execução, um banco de dados será criado automaticamente no mesmo diretório do executável

## Observações

- Os certificados próximos ao vencimento (30 dias ou menos) aparecerão em laranja
- Os certificados vencidos aparecerão em vermelho
- Os dados são armazenados localmente em um banco de dados SQLite 