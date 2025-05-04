# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.models.models import OLT, ONU, LogEntry
from app import db
import datetime
from collections import Counter
import re # Import regex for parsing

# Importar funções de coleta SNMP
from app.snmp_utils import get_olt_info, get_ont_list
# Importar função de execução SSH
from app.ssh_utils import execute_olt_command

main_bp = Blueprint("main", __name__)

# Cache simples para dados SNMP (evita coletas repetidas em curto intervalo)
_snmp_cache = {
    "olt_info": None,
    "ont_list": None,
    "last_fetch_time": None
}
CACHE_TIMEOUT_SECONDS = 60 # Atualiza a cada 60 segundos

def _get_cached_snmp_data():
    """Retorna dados SNMP do cache se válidos, senão busca novos."""
    now = datetime.datetime.now()
    cache_valid = False
    if _snmp_cache["last_fetch_time"]:
        if (now - _snmp_cache["last_fetch_time"]).total_seconds() < CACHE_TIMEOUT_SECONDS:
            cache_valid = True

    if cache_valid and _snmp_cache["olt_info"] is not None and _snmp_cache["ont_list"] is not None:
        # print("Usando cache SNMP") # Debug
        return _snmp_cache["olt_info"], _snmp_cache["ont_list"]
    else:
        # print("Buscando novos dados SNMP") # Debug
        olt_info = get_olt_info()
        ont_list_snmp = get_ont_list()
        _snmp_cache["olt_info"] = olt_info
        _snmp_cache["ont_list"] = ont_list_snmp
        _snmp_cache["last_fetch_time"] = now
        return olt_info, ont_list_snmp

@main_bp.route("/")
@main_bp.route("/index")
@login_required
def index():
    """
    Página inicial do dashboard
    """
    # Obter informações básicas para o dashboard (do banco de dados)
    olts = OLT.query.all()
    total_olts = len(olts)

    # Obter logs recentes
    recent_logs = LogEntry.query.order_by(LogEntry.timestamp.desc()).limit(10).all()

    # Coletar informações da OLT e ONTs via SNMP (usando cache)
    olt_info, ont_list_snmp = _get_cached_snmp_data()

    ont_categories = Counter() # Para contar ONTs por categoria
    error_ont_fetch = False

    # Verificar se houve erro na coleta
    if isinstance(ont_list_snmp, dict) and ont_list_snmp.get("error"):
        flash(f"Erro ao buscar lista de ONTs: {ont_list_snmp['error']}", "danger")
        ont_list_data = [] # Passa lista vazia para o template em caso de erro
        error_ont_fetch = True
        _snmp_cache["ont_list"] = [] # Limpa cache em caso de erro
    elif isinstance(olt_info, dict) and olt_info.get("error"):
         flash(f"Erro ao buscar informações da OLT: {olt_info['error']}", "danger")
         # Mantém a lista de ONTs se ela foi obtida com sucesso
         ont_list_data = ont_list_snmp if isinstance(ont_list_snmp, list) else []
         if not isinstance(ont_list_snmp, list):
             error_ont_fetch = True # Marca erro se a lista de ONTs também falhou
    else:
        ont_list_data = ont_list_snmp
        # Calcular contagens por categoria apenas se a lista for válida
        for ont in ont_list_data:
            category = ont.get("category", "Desconhecido")
            ont_categories[category] += 1

    # Calcular contagens gerais (Online/Offline/Total)
    total_onus_snmp = len(ont_list_data)
    online_onus_snmp = sum(ont_categories[cat] for cat in ont_categories if cat.startswith("Online") or cat == "Sinal Baixo/Crítico" or cat == "Sinal Muito Baixo (Falha?)")
    offline_onus_snmp = ont_categories["Offline"]

    # Define a ordem desejada das categorias para exibição
    category_order = [
        "Online (Sinal OK)",
        "Sinal Baixo/Crítico",
        "Sinal Muito Baixo (Falha?)",
        "Offline",
        "Esperando Provisionamento",
        "Online (Sinal Desconhecido)",
        "Desconhecido"
    ]

    # Cria uma lista ordenada de tuplas (categoria, contagem) para passar ao template
    ordered_categories = [(cat, ont_categories.get(cat, 0)) for cat in category_order if ont_categories.get(cat, 0) > 0]

    return render_template("index.html",
                          title="Dashboard",
                          total_olts=total_olts,
                          total_onus=total_onus_snmp,
                          online_onus=online_onus_snmp,
                          offline_onus=offline_onus_snmp,
                          recent_logs=recent_logs,
                          olts=olts,
                          olt_info=olt_info,
                          ont_list=ont_list_data, # Passa a lista completa inicialmente
                          ont_categories=ordered_categories,
                          error_ont_fetch=error_ont_fetch)

@main_bp.route("/api/onus")
@login_required
def api_onus():
    """Retorna a lista de ONUs, opcionalmente filtrada por categoria."""
    category_filter = request.args.get("category")

    # Obtem dados do cache ou busca novos
    _, ont_list_snmp = _get_cached_snmp_data()

    if isinstance(ont_list_snmp, dict) and ont_list_snmp.get("error"):
        return jsonify({"error": f"Erro ao buscar ONUs: {ont_list_snmp['error']}"}), 500

    if not isinstance(ont_list_snmp, list):
         return jsonify({"error": "Formato inesperado para lista de ONUs."}), 500

    # Filtra a lista se uma categoria foi especificada
    if category_filter and category_filter != "all":
        filtered_list = [ont for ont in ont_list_snmp if ont.get("category") == category_filter]
    else:
        filtered_list = ont_list_snmp # Retorna todos se filtro for "all" ou não especificado

    return jsonify(filtered_list)

@main_bp.route("/api/authorize_ont", methods=["POST"])
@login_required
def api_authorize_ont():
    """Autoriza uma ONT na OLT via CLI/SSH."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Requisição inválida."}), 400

    if_index = data.get("if_index")
    serial_number = data.get("serial_number")
    description = data.get("description", "Autorizado via OLT Manager") # Descrição padrão
    # TODO: Adicionar line_profile_id e srv_profile_id se necessário
    line_profile_id = data.get("line_profile_id", 1) # Exemplo: Padrão 1
    srv_profile_id = data.get("srv_profile_id", 1)   # Exemplo: Padrão 1

    if not if_index or not serial_number:
        return jsonify({"error": "ifIndex e serialNumber são obrigatórios."}), 400

    # 1. Extrair porta PON do ifIndex (Exemplo: ifIndex 16843008 -> 0/1/0)
    # A lógica exata depende do mapeamento ifIndex -> porta física da Huawei
    # Vamos assumir uma função hipotética get_port_from_ifindex
    # Esta função precisa ser implementada corretamente!
    # Exemplo SIMPLIFICADO (NÃO FUNCIONAL PARA HUAWEI REAL):
    try:
        # Tentativa de extrair slot/porta/ont_id de um ifIndex hipotético
        # A Huawei usa um esquema diferente, isso precisa ser ajustado!
        # Ex: 16777216 + slot*1048576 + port*65536 + ont_id
        # Ou pode ser mais simples dependendo da MIB usada para ifIndex
        # Vamos usar uma lógica placeholder
        # ifIndex 16843008 -> 0/1/0 (Exemplo)
        # ifIndex 16908544 -> 0/2/0 (Exemplo)
        # ifIndex 16843009 -> 0/1/1 (Exemplo)

        # Placeholder: Extrair porta e ont_id do ifIndex (PRECISA DE AJUSTE REAL)
        # Supondo que ifIndex seja um número que possamos mapear
        # Esta lógica é apenas um exemplo e provavelmente incorreta para Huawei
        base_ifindex = 16777216 # Exemplo
        slot_offset = 1048576
        port_offset = 65536
        ont_offset = 1

        relative_index = int(if_index) - base_ifindex
        slot = relative_index // slot_offset
        port_in_slot = (relative_index % slot_offset) // port_offset
        ont_id_from_ifindex = (relative_index % port_offset) // ont_offset

        # Formato CLI: frame/slot/port (assumindo frame 0)
        cli_port = f"0/{slot}/{port_in_slot}"
        # Usar o próximo ID disponível ou o ID do ifIndex? Vamos usar o do ifIndex por enquanto
        ont_id = ont_id_from_ifindex
        current_app.logger.info(f"Mapeado ifIndex {if_index} para Porta CLI: {cli_port}, ONT ID: {ont_id}")

    except Exception as e:
        current_app.logger.error(f"Erro ao mapear ifIndex {if_index}: {e}")
        return jsonify({"error": f"Erro ao processar ifIndex: {e}"}), 500

    # 2. Construir comandos CLI
    commands = [
        "config",
        f"interface gpon {cli_port}",
        f"ont add {ont_id} sn-auth {serial_number} omci ont-lineprofile-id {line_profile_id} ont-srvprofile-id {srv_profile_id} desc \"{description}\"",
        "quit", # Sai do modo interface
        "quit"  # Sai do modo config
    ]

    # 3. Executar comandos via SSH
    full_output = ""
    final_error = None
    for cmd in commands:
        output, error = execute_olt_command(cmd)
        if output:
            full_output += output + "\n"
        if error:
            final_error = f"Erro ao executar '{cmd}': {error}"
            current_app.logger.error(final_error)
            # Tentar sair dos modos de configuração em caso de erro
            execute_olt_command("quit")
            execute_olt_command("quit")
            break # Interrompe a sequência de comandos
        # Pequena pausa entre comandos
        time.sleep(0.5)

    # 4. Verificar resultado e retornar
    if final_error:
        return jsonify({"error": final_error, "output": full_output}), 500
    else:
        # Verificar se a saída contém mensagens de sucesso ou erro específicas da OLT
        if "success" in full_output.lower() or "operation successful" in full_output.lower():
             # Forçar atualização do cache SNMP após autorização bem-sucedida
            _snmp_cache["ont_list"] = None
            _snmp_cache["last_fetch_time"] = None
            current_app.logger.info(f"ONT {serial_number} autorizada com sucesso na porta {cli_port} ID {ont_id}.")
            return jsonify({"message": "ONT autorizada com sucesso!", "output": full_output}), 200
        elif "failure" in full_output.lower() or "error" in full_output.lower():
             current_app.logger.warning(f"Comando executado, mas OLT reportou falha/erro para ONT {serial_number}. Saída: {full_output}")
             return jsonify({"error": "Comando executado, mas OLT reportou falha/erro.", "output": full_output}), 500
        else:
            # Forçar atualização do cache SNMP mesmo se não houver confirmação explícita
            _snmp_cache["ont_list"] = None
            _snmp_cache["last_fetch_time"] = None
            current_app.logger.info(f"Comandos de autorização para ONT {serial_number} executados. Verifique o status da ONT. Saída: {full_output}")
            return jsonify({"message": "Comandos de autorização executados. Verifique o status da ONT.", "output": full_output}), 200 # Retorna 200 mas com aviso

@main_bp.route("/about")
def about():
    """
    Página sobre o sistema
    """
    return render_template("about.html", title="Sobre")

@main_bp.route("/refresh_data")
@login_required
def refresh_data():
    """
    Força a atualização dos dados SNMP limpando o cache e redireciona para o dashboard.
    """
    _snmp_cache["olt_info"] = None
    _snmp_cache["ont_list"] = None
    _snmp_cache["last_fetch_time"] = None
    flash("Forçando atualização dos dados SNMP...", "info")
    return redirect(url_for("main.index"))

