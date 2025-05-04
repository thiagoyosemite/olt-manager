#!/bin/bash

# Script de instalação do OLT Manager
# Este script configura o ambiente e instala todas as dependências necessárias

echo "=== Iniciando instalação do OLT Manager ==="
echo "Este script irá configurar o ambiente e instalar todas as dependências necessárias."

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then
  echo "Por favor, execute este script como root ou usando sudo."
  exit 1
fi

# Atualizar o sistema
echo "Atualizando o sistema..."
apt update && apt upgrade -y

# Instalar dependências
echo "Instalando dependências..."
apt install -y python3-pip python3-venv git sqlite3

# Criar diretório para logs
echo "Configurando diretórios..."
mkdir -p /var/log/olt-manager
chmod 755 /var/log/olt-manager

# Criar usuário para o serviço (opcional)
echo "Deseja criar um usuário dedicado para o OLT Manager? (s/n)"
read -r create_user

if [ "$create_user" = "s" ] || [ "$create_user" = "S" ]; then
  echo "Criando usuário 'oltmanager'..."
  useradd -m -s /bin/bash oltmanager
  
  # Definir diretório de instalação
  INSTALL_DIR="/home/oltmanager/olt-manager"
  mkdir -p "$INSTALL_DIR"
  cp -r ./* "$INSTALL_DIR/"
  chown -R oltmanager:oltmanager "$INSTALL_DIR"
  chown -R oltmanager:oltmanager /var/log/olt-manager
else
  # Usar diretório atual
  INSTALL_DIR=$(pwd)
fi

# Criar ambiente virtual Python
echo "Configurando ambiente virtual Python..."
cd "$INSTALL_DIR" || exit 1

if [ "$create_user" = "s" ] || [ "$create_user" = "S" ]; then
  su - oltmanager -c "cd $INSTALL_DIR && python3 -m venv venv"
  su - oltmanager -c "cd $INSTALL_DIR && source venv/bin/activate && pip install -r requirements.txt"
else
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
fi

# Configurar arquivo .env
echo "Configurando arquivo .env..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
  cat > "$INSTALL_DIR/.env" << EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))")
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

  if [ "$create_user" = "s" ] || [ "$create_user" = "S" ]; then
    chown oltmanager:oltmanager "$INSTALL_DIR/.env"
  fi
  
  echo "Arquivo .env criado com configurações padrão."
  echo "Por favor, edite o arquivo .env para configurar suas credenciais e endereços específicos."
else
  echo "Arquivo .env já existe. Mantendo configurações existentes."
fi

# Inicializar banco de dados
echo "Inicializando banco de dados..."
if [ "$create_user" = "s" ] || [ "$create_user" = "S" ]; then
  su - oltmanager -c "cd $INSTALL_DIR && source venv/bin/activate && flask db init"
  su - oltmanager -c "cd $INSTALL_DIR && source venv/bin/activate && flask db migrate -m 'Estrutura inicial do banco de dados'"
  su - oltmanager -c "cd $INSTALL_DIR && source venv/bin/activate && flask db upgrade"
else
  source venv/bin/activate
  flask db init
  flask db migrate -m "Estrutura inicial do banco de dados"
  flask db upgrade
fi

# Criar serviço systemd
echo "Configurando serviço systemd..."
cat > /etc/systemd/system/olt-manager.service << EOF
[Unit]
Description=OLT Manager Service
After=network.target

[Service]
User=$([ "$create_user" = "s" ] || [ "$create_user" = "S" ] && echo "oltmanager" || echo "$USER")
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 run:app
Restart=always
StandardOutput=append:/var/log/olt-manager/stdout.log
StandardError=append:/var/log/olt-manager/stderr.log

[Install]
WantedBy=multi-user.target
EOF

# Recarregar systemd
systemctl daemon-reload

# Iniciar serviço
echo "Deseja iniciar o serviço OLT Manager agora? (s/n)"
read -r start_service

if [ "$start_service" = "s" ] || [ "$start_service" = "S" ]; then
  echo "Iniciando serviço..."
  systemctl start olt-manager
  systemctl enable olt-manager
  echo "Serviço iniciado e configurado para iniciar automaticamente."
else
  echo "O serviço não foi iniciado. Você pode iniciá-lo manualmente com:"
  echo "  sudo systemctl start olt-manager"
  echo "Para habilitar o início automático na inicialização do sistema:"
  echo "  sudo systemctl enable olt-manager"
fi

echo ""
echo "=== Instalação do OLT Manager concluída ==="
echo "O sistema está instalado em: $INSTALL_DIR"
echo "Acesse a interface web em: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Consulte a documentação em $INSTALL_DIR/docs/ para mais informações."
echo "Em caso de problemas, verifique os logs em /var/log/olt-manager/"
