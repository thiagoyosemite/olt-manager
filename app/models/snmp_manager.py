from pysnmp.hlapi import *

class SNMPManager:
    def __init__(self, host, community, port=161, version='2c'):
        self.host = host
        self.community = community
        self.port = port
        self.version = version
        
    def get_snmp_data(self, oid):
        """
        Obtém um valor SNMP específico baseado no OID
        """
        if self.version == '2c':
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication:
                return None, f"Erro: {errorIndication}"
            elif errorStatus:
                return None, f"Erro: {errorStatus.prettyPrint()} em {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
            else:
                for varBind in varBinds:
                    return varBind[1], None
        
        return None, "Versão SNMP não suportada"
    
    def walk_snmp_data(self, oid):
        """
        Realiza um SNMP walk em um OID específico
        """
        result = []
        
        if self.version == '2c':
            for (errorIndication,
                 errorStatus,
                 errorIndex,
                 varBinds) in nextCmd(
                    SnmpEngine(),
                    CommunityData(self.community),
                    UdpTransportTarget((self.host, self.port)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                    lexicographicMode=False):
                
                if errorIndication:
                    return None, f"Erro: {errorIndication}"
                elif errorStatus:
                    return None, f"Erro: {errorStatus.prettyPrint()} em {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
                else:
                    for varBind in varBinds:
                        result.append((str(varBind[0]), varBind[1]))
            
            return result, None
        
        return None, "Versão SNMP não suportada"
    
    def set_snmp_data(self, oid, value_type, value):
        """
        Define um valor SNMP para um OID específico
        """
        if self.version == '2c':
            if value_type == 'Integer':
                val = Integer(value)
            elif value_type == 'OctetString':
                val = OctetString(value)
            elif value_type == 'Counter32':
                val = Counter32(value)
            elif value_type == 'Counter64':
                val = Counter64(value)
            elif value_type == 'Gauge32':
                val = Gauge32(value)
            elif value_type == 'IpAddress':
                val = IpAddress(value)
            else:
                return False, "Tipo de valor não suportado"
            
            iterator = setCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(oid), val)
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication:
                return False, f"Erro: {errorIndication}"
            elif errorStatus:
                return False, f"Erro: {errorStatus.prettyPrint()} em {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
            else:
                return True, None
        
        return False, "Versão SNMP não suportada"

class HuaweiOLTManager:
    """
    Classe específica para gerenciamento de OLTs Huawei MA5800-X7 via SNMP
    """
    def __init__(self, snmp_manager):
        self.snmp = snmp_manager
        
        # OIDs comuns para Huawei MA5800-X7
        # Estes são exemplos e precisam ser ajustados com os OIDs corretos
        self.oids = {
            'system_name': '1.3.6.1.2.1.1.5.0',
            'system_description': '1.3.6.1.2.1.1.1.0',
            'system_uptime': '1.3.6.1.2.1.1.3.0',
            'interfaces': '1.3.6.1.2.1.2.2.1',
            'onu_list': '1.3.6.1.4.1.2011.6.128.1.1.2.43.1.3',  # Exemplo, precisa ser verificado
            'onu_status': '1.3.6.1.4.1.2011.6.128.1.1.2.43.1.8',  # Exemplo, precisa ser verificado
            'onu_signal': '1.3.6.1.4.1.2011.6.128.1.1.2.51.1.4'  # Exemplo, precisa ser verificado
        }
    
    def get_system_info(self):
        """
        Obtém informações básicas do sistema
        """
        name, err = self.snmp.get_snmp_data(self.oids['system_name'])
        if err:
            return None, err
            
        description, err = self.snmp.get_snmp_data(self.oids['system_description'])
        if err:
            return None, err
            
        uptime, err = self.snmp.get_snmp_data(self.oids['system_uptime'])
        if err:
            return None, err
            
        return {
            'name': str(name),
            'description': str(description),
            'uptime': str(uptime)
        }, None
    
    def get_onu_list(self):
        """
        Obtém a lista de ONUs conectadas
        """
        onus, err = self.snmp.walk_snmp_data(self.oids['onu_list'])
        if err:
            return None, err
            
        onu_list = []
        for oid, value in onus:
            # Extrair informações da ONU do OID e valor
            # Este é um exemplo e precisa ser ajustado com base nos OIDs reais
            onu_id = oid.split('.')[-1]
            onu_list.append({
                'id': onu_id,
                'serial': str(value)
            })
            
        return onu_list, None
    
    def get_onu_status(self, onu_id):
        """
        Obtém o status de uma ONU específica
        """
        status_oid = f"{self.oids['onu_status']}.{onu_id}"
        status, err = self.snmp.get_snmp_data(status_oid)
        if err:
            return None, err
            
        # Mapear o valor numérico para um status legível
        status_map = {
            '1': 'online',
            '2': 'offline',
            '3': 'disabled',
            '4': 'unknown'
        }
        
        status_str = status_map.get(str(status), 'unknown')
        
        return status_str, None
    
    def get_onu_signal(self, onu_id):
        """
        Obtém o nível de sinal de uma ONU específica
        """
        signal_oid = f"{self.oids['onu_signal']}.{onu_id}"
        signal, err = self.snmp.get_snmp_data(signal_oid)
        if err:
            return None, err
            
        # Converter o valor para dBm (pode variar dependendo do equipamento)
        # Este é um exemplo e precisa ser ajustado
        signal_dbm = float(signal) / 10.0
        
        return signal_dbm, None
    
    def enable_onu(self, onu_id):
        """
        Habilita uma ONU específica
        """
        status_oid = f"{self.oids['onu_status']}.{onu_id}"
        success, err = self.snmp.set_snmp_data(status_oid, 'Integer', 1)  # 1 = habilitar (exemplo)
        return success, err
    
    def disable_onu(self, onu_id):
        """
        Desabilita uma ONU específica
        """
        status_oid = f"{self.oids['onu_status']}.{onu_id}"
        success, err = self.snmp.set_snmp_data(status_oid, 'Integer', 3)  # 3 = desabilitar (exemplo)
        return success, err
