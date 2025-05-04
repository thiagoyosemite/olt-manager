# OLT Manager - Documentação do Usuário

## Visão Geral

OLT Manager é uma solução personalizada para gerenciamento de OLTs Huawei MA5800-X7 e ONTs associadas. O sistema oferece uma interface web intuitiva para monitoramento e configuração de equipamentos de rede óptica, incluindo funcionalidades avançadas de gerenciamento via SNMP e TR-069.

## Características Principais

- **Dashboard intuitivo** com visão geral do status da OLT e ONUs
- **Gerenciamento de OLT** via SNMP
- **Gerenciamento de ONTs** via TR-069
- **Monitoramento de sinal** e status das ONUs
- **Provisionamento automático** de novas ONUs
- **Configuração remota** de parâmetros Wi-Fi, VoIP e outros
- **Diagnósticos** de conectividade
- **Atualização de firmware** remota
- **Sistema de logs** para rastreamento de eventos

## Requisitos do Sistema

- Sistema operacional: Linux (Ubuntu 20.04 ou superior recomendado)
- Python 3.8 ou superior
- Banco de dados SQLite (padrão) ou PostgreSQL/MySQL (opcional)
- Acesso à rede para comunicação com a OLT via SNMP
- Servidor com pelo menos 2GB de RAM e 10GB de espaço em disco

## Instalação

### 1. Preparação do Ambiente

```bash
# Atualizar o sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependências
sudo apt install -y python3-pip python3-venv git

# Clonar o repositório (se disponível em um repositório Git)
git clone https://github.com/seu-usuario/olt-manager.git
cd olt-manager

# Ou descompactar o arquivo zip fornecido
# unzip olt-manager.zip
# cd olt-manager
```

### 2. Configuração do Ambiente Virtual

```bash
# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 3. Configuração Inicial

```bash
# Criar arquivo .env com configurações
cat > .env << EOF
SECRET_KEY=chave-secreta-personalizada
FLASK_APP=run.py
FLASK_ENV=production

# Configurações SNMP para OLT
SNMP_HOST=192.168.1.1
SNMP_PORT=161
SNMP_COMMUNITY=public
SNMP_VERSION=2c

# Configurações do servidor TR-069 ACS
TR069_ACS_HOST=0.0.0.0
TR069_ACS_PORT=7547
TR069_ACS_USERNAME=admin
TR069_ACS_PASSWORD=senha-segura
EOF

# Inicializar banco de dados
flask db init
flask db migrate -m "Estrutura inicial do banco de dados"
flask db upgrade

# Criar usuário administrador
flask create-admin
```

### 4. Execução do Sistema

```bash
# Iniciar o servidor em modo de desenvolvimento
flask run --host=0.0.0.0 --port=5000

# Para produção, recomenda-se usar Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

## Configuração da OLT

Para que o sistema possa gerenciar sua OLT Huawei MA5800-X7, é necessário configurar o acesso SNMP:

1. Acesse a interface de linha de comando da OLT
2. Configure a community SNMP:

```
snmp-agent community read public
snmp-agent community write private
```

3. Habilite o SNMP:

```
snmp-agent sys-info version v2c
snmp-agent trap enable
```

## Configuração do TR-069 para ONTs

Para utilizar as funcionalidades TR-069, é necessário:

1. Acessar o sistema OLT Manager
2. Navegar para a seção TR-069 > Configurações do ACS
3. Configurar o endereço IP e porta do servidor ACS
4. Iniciar o servidor ACS
5. Configurar as ONTs para apontarem para o servidor ACS:
   - Isso pode ser feito via SNMP ou manualmente em cada ONT

## Uso do Sistema

### Login e Dashboard

1. Acesse o sistema através do navegador: `http://seu-servidor:5000`
2. Faça login com as credenciais de administrador
3. O dashboard exibirá informações gerais sobre a OLT e ONUs

### Gerenciamento de OLT

1. Acesse a seção "OLTs" no menu principal
2. Adicione sua OLT Huawei MA5800-X7 com o endereço IP e community SNMP
3. Clique em "Atualizar" para obter informações atualizadas da OLT

### Gerenciamento de ONUs

1. Acesse a seção "ONUs" no menu principal
2. Visualize todas as ONUs descobertas
3. Clique em uma ONU específica para gerenciá-la
4. Opções disponíveis:
   - Habilitar/Desabilitar ONU
   - Visualizar informações de sinal
   - Acessar configurações TR-069

### Funcionalidades TR-069

1. Acesse a seção "TR-069" no menu principal
2. Inicie o servidor ACS se ainda não estiver em execução
3. Selecione um dispositivo para gerenciar
4. Opções disponíveis:
   - Configuração Wi-Fi
   - Configuração VoIP
   - Atualização de Firmware
   - Diagnósticos
   - Reinicialização

## Solução de Problemas

### Problemas de Conexão SNMP

Se o sistema não conseguir se comunicar com a OLT via SNMP:

1. Verifique se a OLT está acessível na rede (teste com ping)
2. Confirme se as configurações SNMP estão corretas (community, versão)
3. Verifique se não há firewalls bloqueando a comunicação na porta 161/UDP

### Problemas com TR-069

Se as ONTs não aparecerem no servidor ACS:

1. Verifique se o servidor ACS está em execução
2. Confirme se as ONTs estão configuradas para apontar para o servidor ACS correto
3. Verifique se não há firewalls bloqueando a comunicação na porta 7547/TCP

### Logs do Sistema

Para verificar os logs do sistema:

1. Acesse a interface web e navegue até a seção de Logs
2. Ou verifique os logs do servidor diretamente:
   ```bash
   tail -f /var/log/olt-manager/app.log
   ```

## Backup e Restauração

### Backup do Banco de Dados

```bash
# Para SQLite (padrão)
cp instance/app.db backup/app.db.$(date +%Y%m%d)

# Para PostgreSQL
pg_dump -U usuario -d olt_manager > backup/olt_manager_$(date +%Y%m%d).sql
```

### Restauração do Banco de Dados

```bash
# Para SQLite (padrão)
cp backup/app.db.20250422 instance/app.db

# Para PostgreSQL
psql -U usuario -d olt_manager < backup/olt_manager_20250422.sql
```

## Segurança

Recomendações de segurança:

1. Altere a chave secreta (SECRET_KEY) no arquivo .env
2. Use senhas fortes para todos os usuários
3. Altere as communities SNMP padrão
4. Configure HTTPS para acesso à interface web
5. Implemente um firewall para limitar o acesso às portas do sistema
6. Realize backups regulares do banco de dados

## Suporte e Contato

Para obter suporte ou relatar problemas, entre em contato através de:

- Email: suporte@exemplo.com
- GitHub: https://github.com/seu-usuario/olt-manager/issues

## Licença

Este software é fornecido sob a licença MIT. Consulte o arquivo LICENSE para mais detalhes.
