import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-padrao-deve-ser-alterada'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configurações SNMP
    SNMP_HOST = os.environ.get('SNMP_HOST') or '192.168.1.1'
    SNMP_PORT = int(os.environ.get('SNMP_PORT') or 161)
    SNMP_COMMUNITY = os.environ.get('SNMP_COMMUNITY') or 'public'
    SNMP_VERSION = os.environ.get('SNMP_VERSION') or '2c'
    
    # Configurações da aplicação
    OLT_MODEL = os.environ.get('OLT_MODEL') or 'MA5800-X7'
    OLT_VENDOR = os.environ.get('OLT_VENDOR') or 'Huawei'
    REFRESH_INTERVAL = int(os.environ.get('REFRESH_INTERVAL') or 60)  # segundos
