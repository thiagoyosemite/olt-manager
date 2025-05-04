# -*- coding: utf-8 -*-
"""Utilitários para coleta de dados SNMP da OLT."""

import os
import re
from pysnmp.hlapi import (
    getCmd, nextCmd, SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity, Integer32
)
from pysnmp.entity.rfc3413.oneliner import cmdgen
import time # Para o uptime

# --- Constantes de Limite --- #
RX_POWER_CRITICAL_THRESHOLD = -28.0 # dBm - Abaixo disso é considerado baixo/crítico
RX_POWER_VERY_LOW_THRESHOLD = -35.0 # dBm - Abaixo disso pode indicar problema físico

# --- OIDs Gerais --- #
OID_SYS_DESCR = '1.3.6.1.2.1.1.1.0'
OID_SYS_UPTIME = '1.3.6.1.2.1.1.3.0'

# --- OIDs de Entidade (ENTITY-MIB & HUAWEI-ENTITY-EXTENT-MIB) --- #
OID_ENT_PHYSICAL_TABLE = '1.3.6.1.2.1.47.1.1.1.1'
OID_ENT_PHYSICAL_DESCR = OID_ENT_PHYSICAL_TABLE + '.2'
OID_ENT_PHYSICAL_CLASS = OID_ENT_PHYSICAL_TABLE + '.5'
OID_ENT_PHYSICAL_MODEL = OID_ENT_PHYSICAL_TABLE + '.13'
OID_HW_ENTITY_STATE_TABLE = '1.3.6.1.4.1.2011.5.25.31.1.1.1'
OID_HW_ENTITY_TEMP = OID_HW_ENTITY_STATE_TABLE + '.1.5'
OID_HW_ENTITY_SW_REV = OID_HW_ENTITY_STATE_TABLE + '.1.7'

# --- OIDs de Interface (IF-MIB) --- #
OID_IF_TABLE = '1.3.6.1.2.1.2.2.1'
OID_IF_DESCR = OID_IF_TABLE + '.2' # Descrição da Interface (ex: GE0/2/0, PON0/6/0)
OID_IF_TYPE = OID_IF_TABLE + '.3' # Tipo da Interface (ex: ethernetCsmacd(6), gpon(237))
OID_IF_ADMIN_STATUS = OID_IF_TABLE + '.7' # Status Administrativo (up(1), down(2), testing(3))
OID_IF_OPER_STATUS = OID_IF_TABLE + '.8' # Status Operacional (up(1), down(2), testing(3), unknown(4), dormant(5), notPresent(6), lowerLayerDown(7))

# --- OIDs de ONU/ONT (HUAWEI-GONU-MIB) --- #
# Tabela de Autenticação/Informações da ONU (hwGonuAuthTable)
OID_HW_GONU_AUTH_TABLE = '1.3.6.1.4.1.2011.5.104.1.4.1.1'
OID_HW_GONU_SERIAL_NUMBER = OID_HW_GONU_AUTH_TABLE + '.1.1' # Octet String
OID_HW_GONU_LOID = OID_HW_GONU_AUTH_TABLE + '.1.4' # Octet String

# Tabela de Status da ONU (hwGonuStatusTable)
OID_HW_GONU_STATUS_TABLE = '1.3.6.1.4.1.2011.5.104.1.1.1.1'
OID_HW_GONU_LINK_STATUS = OID_HW_GONU_STATUS_TABLE + '.1.1' # Integer: online(1), offline(2), unknown(3)
OID_HW_GONU_REG_STATUS = OID_HW_GONU_STATUS_TABLE + '.1.2' # Integer: registered(1), unregistered(2), unknown(3)
OID_HW_GONU_RX_POWER = OID_HW_GONU_STATUS_TABLE + '.1.9' # Integer32: Potência em 0.01 dBm
OID_HW_GONU_TX_POWER = OID_HW_GONU_STATUS_TABLE + '.1.8' # Integer32: Potência em 0.01 dBm

# --- Funções Auxiliares --- #

def snmp_walk(target_ip, community, oids):
    """Realiza um SNMP WALK (nextCmd) para um ou mais OIDs base."""
    results = {}
    cmdGen = cmdgen.CommandGenerator()
    errorIndication, errorStatus, errorIndex, varBindTable = cmdGen.nextCmd(
        cmdgen.CommunityData(community, mpModel=1),
        cmdgen.UdpTransportTarget((target_ip, 161)),
        *[cmdgen.MibVariable(oid) for oid in oids],
        lexicographicMode=False
    )

    if errorIndication:
        print(f"Erro SNMP WALK: {errorIndication}")
        return None
    elif errorStatus:
        print(f"Erro SNMP WALK: {errorStatus.prettyPrint()} at {errorIndex and varBindTable[int(errorIndex)-1][0] or '?'}")
        return None
    else:
        for varBindTableRow in varBindTable:
            for name, val in varBindTableRow:
                oid_str = str(name)
                # Tenta decodificar se for OctetString, senão usa a representação padrão
                try:
                    results[oid_str] = val.prettyPrint()
                except AttributeError:
                    results[oid_str] = str(val)
        return results

def get_interface_map(target_ip, community):
    """Cria um mapa de ifIndex para descrição da interface."""
    if_map = {}
    if_data = snmp_walk(target_ip, community, [OID_IF_DESCR])
    if if_data:
        for oid, descr in if_data.items():
            if oid.startswith(OID_IF_DESCR + '.'):
                try:
                    if_index = int(oid.split('.')[-1])
                    if_map[if_index] = descr
                except ValueError:
                    continue # Ignora OIDs malformados
    return if_map

def parse_rx_power(power_str):
    """Converte a string de potência Rx (ex: '-15.23 dBm') para float."""
    if not isinstance(power_str, str) or 'dBm' not in power_str:
        return None
    try:
        # Extrai o número usando regex para mais robustez
        match = re.match(r"(-?\[0-9\.]+)\s*dBm", power_str)
        if match:
            return float(match.group(1))
        else:
            return None
    except (ValueError, TypeError):
        return None

def categorize_ont(ont_data):
    """Classifica uma ONU em uma categoria com base em seus dados."""
    link_status = ont_data.get('linkStatus')
    reg_status = ont_data.get('regStatus')
    rx_power_str = ont_data.get('rxPower')
    rx_power_float = parse_rx_power(rx_power_str)

    if reg_status == 'unregistered':
        return 'Esperando Provisionamento'
    elif link_status == 'offline':
        return 'Offline'
    elif link_status == 'online' and reg_status == 'registered':
        if rx_power_float is not None:
            if rx_power_float < RX_POWER_VERY_LOW_THRESHOLD:
                return 'Sinal Muito Baixo (Falha?)'
            elif rx_power_float < RX_POWER_CRITICAL_THRESHOLD:
                return 'Sinal Baixo/Crítico'
            else:
                return 'Online (Sinal OK)'
        else:
            return 'Online (Sinal Desconhecido)' # Caso não consiga ler o RxPower
    else:
        return 'Desconhecido'

# --- Funções de Coleta Principais --- #

def get_snmp_data(target_ip, community, oids):
    """Busca um ou mais OIDs específicos via SNMP GET."""
    results = {}
    error_indication, error_status, error_index, var_binds = next(
        getCmd(SnmpEngine(),
               CommunityData(community, mpModel=1),
               UdpTransportTarget((target_ip, 161)),
               ContextData(),
               *[ObjectType(ObjectIdentity(oid)) for oid in oids])
    )

    if error_indication:
        print(f"Erro SNMP GET: {error_indication}")
        return None
    elif error_status:
        print(f"Erro SNMP GET: {error_status.prettyPrint()} at {error_index and var_binds[int(error_index) - 1][0] or '?'}")
        return None
    else:
        for var_bind in var_binds:
            oid_str = str(var_bind[0])
            value = var_bind[1]
            try:
                results[oid_str] = value.prettyPrint()
            except AttributeError:
                 results[oid_str] = str(value)
        return results

def find_entity_index(target_ip, community, desired_class='chassis', desired_descr_part=None):
    """Encontra o entPhysicalIndex de uma entidade baseado na classe ou descrição."""
    # Reutiliza snmp_walk para simplificar
    entity_data = snmp_walk(target_ip, community, [OID_ENT_PHYSICAL_CLASS, OID_ENT_PHYSICAL_DESCR])
    if not entity_data:
        return None

    found_indices = {}
    # Agrupa por índice
    for oid, value in entity_data.items():
        try:
            parts = oid.split('.')
            index = int(parts[-1])
            base_oid = '.'.join(parts[:-1])
            if index not in found_indices:
                found_indices[index] = {}
            found_indices[index][base_oid] = value
        except (ValueError, IndexError):
            continue

    # Itera sobre os índices encontrados
    for index, data in found_indices.items():
        entity_class = data.get(OID_ENT_PHYSICAL_CLASS, '')
        entity_descr = data.get(OID_ENT_PHYSICAL_DESCR, '')

        class_match = entity_class == desired_class
        descr_match = desired_descr_part and desired_descr_part.lower() in entity_descr.lower()

        if class_match or descr_match:
            print(f"Índice encontrado: {index} (Classe: {entity_class}, Descrição: {entity_descr})")
            return index

    print(f"Nenhum índice encontrado para classe '{desired_class}' ou descrição contendo '{desired_descr_part}'")
    return None

def get_olt_info():
    """Coleta informações básicas da OLT via SNMP."""
    olt_ip = os.environ.get('OLT_IP')
    community = os.environ.get('SNMP_COMMUNITY')

    if not olt_ip or not community:
        print("OLT_IP ou SNMP_COMMUNITY não definidos nas variáveis de ambiente.")
        return {'error': 'Configuração SNMP ausente.'}

    olt_data = {'ip': olt_ip}

    # 1. Obter sysDescr e sysUpTime
    basic_info = get_snmp_data(olt_ip, community, [OID_SYS_DESCR, OID_SYS_UPTIME])
    if basic_info:
        olt_data['sysDescr'] = basic_info.get(OID_SYS_DESCR, 'N/A')
        try:
            uptime_ticks = int(basic_info.get(OID_SYS_UPTIME, 0))
            uptime_seconds = uptime_ticks / 100
            days = int(uptime_seconds // (24 * 3600))
            hours = int((uptime_seconds % (24 * 3600)) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            olt_data['uptime'] = f"{days}d {hours}h {minutes}m"
            olt_data['uptime_seconds'] = uptime_seconds
        except ValueError:
            olt_data['uptime'] = 'Erro na conversão'
            olt_data['uptime_seconds'] = 0
    else:
        olt_data['sysDescr'] = 'Erro ao buscar'
        olt_data['uptime'] = 'Erro ao buscar'
        olt_data['uptime_seconds'] = 0

    # 2. Encontrar índice da entidade principal
    entity_index = find_entity_index(olt_ip, community, desired_class='chassis')
    if not entity_index:
         entity_index = find_entity_index(olt_ip, community, desired_class='container', desired_descr_part='MPLA')
         if not entity_index:
             entity_index = find_entity_index(olt_ip, community, desired_class='module', desired_descr_part='Control')

    if entity_index:
        print(f"Usando índice de entidade: {entity_index}")
        # 3. Obter Modelo, Versão SW e Temperatura
        oids_with_index = [
            f"{OID_ENT_PHYSICAL_MODEL}.{entity_index}",
            f"{OID_HW_ENTITY_SW_REV}.{entity_index}",
            f"{OID_HW_ENTITY_TEMP}.{entity_index}"
        ]
        detailed_info = get_snmp_data(olt_ip, community, oids_with_index)
        if detailed_info:
            olt_data['model'] = detailed_info.get(f"{OID_ENT_PHYSICAL_MODEL}.{entity_index}", 'N/A')
            olt_data['sw_version'] = detailed_info.get(f"{OID_HW_ENTITY_SW_REV}.{entity_index}", 'N/A')
            temp_str = detailed_info.get(f"{OID_HW_ENTITY_TEMP}.{entity_index}", 'N/A')
            olt_data['temperature'] = f"{temp_str} °C" if temp_str != 'N/A' and temp_str.isdigit() else temp_str
        else:
            olt_data['model'] = 'Erro ao buscar'
            olt_data['sw_version'] = 'Erro ao buscar'
            olt_data['temperature'] = 'Erro ao buscar'
    else:
        print("Não foi possível determinar o índice da entidade principal.")
        olt_data['model'] = 'Índice não encontrado'
        olt_data['sw_version'] = 'Índice não encontrado'
        olt_data['temperature'] = 'Índice não encontrado'

    # 4. Extrair informações do sysDescr se possível
    if olt_data['sysDescr'] != 'N/A' and olt_data['sysDescr'] != 'Erro ao buscar':
        descr_parts = olt_data['sysDescr'].split(' ')
        if 'MA5800' in olt_data['sysDescr'] and not olt_data.get('model', '').startswith('MA5800'):
             for part in descr_parts:
                 if part.startswith('MA5800'):
                     olt_data['model'] = part
                     break
        if 'V100R' in olt_data['sysDescr'] and not olt_data.get('sw_version', '').startswith('V100R'):
             for part in descr_parts:
                 if part.startswith('V100R'):
                     olt_data['sw_version'] = part
                     break

    print(f"Dados da OLT coletados: {olt_data}")
    return olt_data

def get_ont_list():
    """Coleta a lista de ONTs/ONUs, seus status e os categoriza via SNMP."""
    olt_ip = os.environ.get('OLT_IP')
    community = os.environ.get('SNMP_COMMUNITY')

    if not olt_ip or not community:
        print("OLT_IP ou SNMP_COMMUNITY não definidos nas variáveis de ambiente.")
        return {'error': 'Configuração SNMP ausente.'}

    onts = {}
    print("Iniciando coleta de interfaces...")
    if_map = get_interface_map(olt_ip, community)
    print(f"Mapa de interfaces obtido: {len(if_map)} entradas.")

    # OIDs a serem buscados no walk
    oids_to_walk = [
        OID_HW_GONU_SERIAL_NUMBER,
        OID_HW_GONU_LOID,
        OID_HW_GONU_LINK_STATUS,
        OID_HW_GONU_REG_STATUS,
        OID_HW_GONU_RX_POWER,
        OID_HW_GONU_TX_POWER
    ]

    print("Iniciando SNMP walk nas tabelas de ONU...")
    walk_data = snmp_walk(olt_ip, community, oids_to_walk)

    if not walk_data:
        print("Falha ao obter dados das tabelas de ONU.")
        return {'error': 'Falha ao obter dados SNMP das ONUs.'}

    print(f"Dados brutos do walk obtidos: {len(walk_data)} entradas.")

    # Processar os dados do walk
    for oid, value in walk_data.items():
        try:
            parts = oid.split('.')
            # O índice da ONU geralmente é composto por ifIndex.onuId
            if len(parts) < 2:
                continue
            onu_id = int(parts[-1])
            if_index = int(parts[-2])
            base_oid = '.'.join(parts[:-2])

            # Cria a entrada para a ONU se não existir
            ont_key = f"{if_index}.{onu_id}"
            if ont_key not in onts:
                onts[ont_key] = {
                    'ifIndex': if_index,
                    'onuId': onu_id,
                    'portName': if_map.get(if_index, f"ifIndex {if_index}"),
                    'serialNumber': 'N/A',
                    'loid': 'N/A',
                    'linkStatus': 'unknown',
                    'regStatus': 'unknown',
                    'rxPower': 'N/A',
                    'txPower': 'N/A',
                    'category': 'Desconhecido' # Inicializa categoria
                }

            # Preenche os dados da ONU
            if base_oid == OID_HW_GONU_SERIAL_NUMBER:
                try:
                    hex_serial = value.replace('0x', '').replace(' ', '')
                    ascii_serial = bytes.fromhex(hex_serial).decode('ascii', errors='ignore')
                    if len(ascii_serial) > 4 and ascii_serial[:4].isalnum() and ascii_serial[:4].isupper():
                         onts[ont_key]['serialNumber'] = ascii_serial
                    else:
                         onts[ont_key]['serialNumber'] = hex_serial
                except Exception as e:
                    print(f"Erro ao formatar serial {value}: {e}")
                    onts[ont_key]['serialNumber'] = value
            elif base_oid == OID_HW_GONU_LOID:
                onts[ont_key]['loid'] = value
            elif base_oid == OID_HW_GONU_LINK_STATUS:
                status_map = {1: 'online', 2: 'offline', 3: 'unknown'}
                onts[ont_key]['linkStatus'] = status_map.get(int(value), 'invalid')
            elif base_oid == OID_HW_GONU_REG_STATUS:
                status_map = {1: 'registered', 2: 'unregistered', 3: 'unknown'}
                onts[ont_key]['regStatus'] = status_map.get(int(value), 'invalid')
            elif base_oid == OID_HW_GONU_RX_POWER:
                try:
                    power_val = float(value) / 100.0
                    onts[ont_key]['rxPower'] = f"{power_val:.2f} dBm"
                except ValueError:
                    onts[ont_key]['rxPower'] = 'Invalid Value'
            elif base_oid == OID_HW_GONU_TX_POWER:
                try:
                    power_val = float(value) / 100.0
                    onts[ont_key]['txPower'] = f"{power_val:.2f} dBm"
                except ValueError:
                    onts[ont_key]['txPower'] = 'Invalid Value'

        except (ValueError, IndexError) as e:
            print(f"Erro ao processar OID {oid} com valor {value}: {e}")
            continue

    # Categorizar ONUs após coletar todos os dados
    for key in onts:
        onts[key]['category'] = categorize_ont(onts[key])

    print(f"Total de ONUs processadas e categorizadas: {len(onts)}")
    # Retorna a lista de dicionários de ONUs
    return list(onts.values())

# --- Teste Local --- #
if __name__ == '__main__':
    # Defina as variáveis de ambiente OLT_IP e SNMP_COMMUNITY
    # Exemplo: export OLT_IP='10.0.0.10'
    #          export SNMP_COMMUNITY='cloudfibertelecom1@'

    print("--- Testando get_olt_info() ---")
    olt_info = get_olt_info()
    if olt_info and not olt_info.get('error'):
        for key, value in olt_info.items():
            print(f"{key}: {value}")
    else:
        print(f"Falha ao coletar informações da OLT: {olt_info.get('error', 'Erro desconhecido')}")

    print("\n--- Testando get_ont_list() ---")
    ont_list = get_ont_list()
    if ont_list and not isinstance(ont_list, dict):
        print(f"Total de ONTs encontradas: {len(ont_list)}")
        # Imprime detalhes das 5 primeiras ONTs como exemplo
        for i, ont in enumerate(ont_list[:5]):
            print(f"\nONT #{i+1}:")
            for key, value in ont.items():
                print(f"  {key}: {value}")
        # Contagem por categoria
        categories = {}
        for ont in ont_list:
            cat = ont.get('category', 'Desconhecido')
            categories[cat] = categories.get(cat, 0) + 1
        print("\nContagem por Categoria:")
        for cat, count in categories.items():
            print(f"  {cat}: {count}")

    elif isinstance(ont_list, dict) and 'error' in ont_list:
         print(f"Falha ao coletar lista de ONTs: {ont_list.get('error', 'Erro desconhecido')}")
    else:
        print("Nenhuma ONT encontrada ou falha na coleta.")

