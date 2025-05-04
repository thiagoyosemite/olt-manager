from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models.models import OLT, ONU, LogEntry
from app.models.tr069_manager import TR069Manager, TR069ACSServer
from app import db
import datetime

tr069_bp = Blueprint('tr069', __name__)

@tr069_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard principal para gerenciamento TR-069
    """
    # Obter estatísticas de dispositivos gerenciados via TR-069
    acs_server = current_app.config.get('TR069_ACS_SERVER')
    if not acs_server:
        flash('Servidor ACS não está configurado', 'warning')
        return render_template('tr069/dashboard.html', title='TR-069 Dashboard', devices=[])
    
    devices = acs_server.get_all_devices()
    
    return render_template('tr069/dashboard.html', 
                          title='TR-069 Dashboard',
                          devices=devices)

@tr069_bp.route('/devices')
@login_required
def device_list():
    """
    Lista todos os dispositivos gerenciados via TR-069
    """
    acs_server = current_app.config.get('TR069_ACS_SERVER')
    if not acs_server:
        flash('Servidor ACS não está configurado', 'warning')
        return render_template('tr069/device_list.html', title='Dispositivos TR-069', devices=[])
    
    devices = acs_server.get_all_devices()
    
    return render_template('tr069/device_list.html', 
                          title='Dispositivos TR-069',
                          devices=devices)

@tr069_bp.route('/device/<device_id>')
@login_required
def device_details(device_id):
    """
    Exibe detalhes de um dispositivo específico
    """
    acs_server = current_app.config.get('TR069_ACS_SERVER')
    if not acs_server:
        flash('Servidor ACS não está configurado', 'warning')
        return redirect(url_for('tr069.device_list'))
    
    device = acs_server.get_device(device_id)
    if not device:
        flash('Dispositivo não encontrado', 'danger')
        return redirect(url_for('tr069.device_list'))
    
    return render_template('tr069/device_details.html', 
                          title=f'Dispositivo: {device_id}',
                          device=device,
                          device_id=device_id)

@tr069_bp.route('/device/<device_id>/wifi', methods=['GET', 'POST'])
@login_required
def wifi_settings(device_id):
    """
    Gerencia configurações Wi-Fi de um dispositivo
    """
    tr069_manager = current_app.config.get('TR069_MANAGER')
    if not tr069_manager:
        flash('Gerenciador TR-069 não está configurado', 'warning')
        return redirect(url_for('tr069.device_details', device_id=device_id))
    
    if request.method == 'POST':
        # Atualizar configurações Wi-Fi
        wifi_settings = {
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.Enable": {
                "value": "1" if request.form.get('wifi_enabled') else "0",
                "type": "xsd:boolean"
            },
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID": {
                "value": request.form.get('ssid', ''),
                "type": "xsd:string"
            },
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.Channel": {
                "value": request.form.get('channel', '0'),
                "type": "xsd:unsignedInt"
            },
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.BeaconType": {
                "value": request.form.get('security_mode', 'None'),
                "type": "xsd:string"
            }
        }
        
        # Adicionar senha se fornecida
        if request.form.get('password'):
            wifi_settings["InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.PreSharedKey.1.PreSharedKey"] = {
                "value": request.form.get('password'),
                "type": "xsd:string"
            }
        
        # Configurações para 5GHz se habilitado
        if request.form.get('wifi_5g_enabled'):
            wifi_settings["InternetGatewayDevice.LANDevice.1.WLANConfiguration.2.Enable"] = {
                "value": "1",
                "type": "xsd:boolean"
            }
            wifi_settings["InternetGatewayDevice.LANDevice.1.WLANConfiguration.2.SSID"] = {
                "value": request.form.get('ssid_5g', ''),
                "type": "xsd:string"
            }
            wifi_settings["InternetGatewayDevice.LANDevice.1.WLANConfiguration.2.Channel"] = {
                "value": request.form.get('channel_5g', '0'),
                "type": "xsd:unsignedInt"
            }
            wifi_settings["InternetGatewayDevice.LANDevice.1.WLANConfiguration.2.BeaconType"] = {
                "value": request.form.get('security_mode_5g', 'None'),
                "type": "xsd:string"
            }
            
            # Adicionar senha 5GHz se fornecida
            if request.form.get('password_5g'):
                wifi_settings["InternetGatewayDevice.LANDevice.1.WLANConfiguration.2.PreSharedKey.1.PreSharedKey"] = {
                    "value": request.form.get('password_5g'),
                    "type": "xsd:string"
                }
        
        success = tr069_manager.set_wifi_settings(device_id, wifi_settings)
        
        if success:
            flash('Configurações Wi-Fi atualizadas com sucesso', 'success')
            
            # Registrar log
            log_entry = LogEntry(
                level='info',
                source=f'TR-069',
                message=f'Configurações Wi-Fi atualizadas para o dispositivo {device_id}'
            )
            db.session.add(log_entry)
            db.session.commit()
        else:
            flash('Erro ao atualizar configurações Wi-Fi', 'danger')
        
        return redirect(url_for('tr069.wifi_settings', device_id=device_id))
    
    # Obter configurações Wi-Fi atuais
    wifi_settings = tr069_manager.get_wifi_settings(device_id)
    
    return render_template('tr069/wifi_settings.html', 
                          title=f'Configurações Wi-Fi: {device_id}',
                          device_id=device_id,
                          wifi_settings=wifi_settings)

@tr069_bp.route('/device/<device_id>/voip', methods=['GET', 'POST'])
@login_required
def voip_settings(device_id):
    """
    Gerencia configurações VoIP de um dispositivo
    """
    tr069_manager = current_app.config.get('TR069_MANAGER')
    if not tr069_manager:
        flash('Gerenciador TR-069 não está configurado', 'warning')
        return redirect(url_for('tr069.device_details', device_id=device_id))
    
    if request.method == 'POST':
        # Atualizar configurações VoIP
        voip_settings = {
            "InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.Enable": {
                "value": "1" if request.form.get('voip_enabled') else "0",
                "type": "xsd:boolean"
            },
            "InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.SIP.ProxyServer": {
                "value": request.form.get('proxy_server', ''),
                "type": "xsd:string"
            },
            "InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.SIP.RegistrarServer": {
                "value": request.form.get('registrar_server', ''),
                "type": "xsd:string"
            },
            "InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.SIP.UserAgentDomain": {
                "value": request.form.get('domain', ''),
                "type": "xsd:string"
            },
            "InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.Line.1.Enable": {
                "value": "1" if request.form.get('line_enabled') else "0",
                "type": "xsd:boolean"
            },
            "InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.Line.1.SIP.AuthUserName": {
                "value": request.form.get('username', ''),
                "type": "xsd:string"
            },
            "InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.Line.1.SIP.URI": {
                "value": request.form.get('uri', ''),
                "type": "xsd:string"
            },
            "InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.Line.1.CallingFeatures.CallerIDName": {
                "value": request.form.get('caller_id', ''),
                "type": "xsd:string"
            }
        }
        
        # Adicionar senha se fornecida
        if request.form.get('password'):
            voip_settings["InternetGatewayDevice.Services.VoiceService.1.VoiceProfile.1.Line.1.SIP.AuthPassword"] = {
                "value": request.form.get('password'),
                "type": "xsd:string"
            }
        
        success = tr069_manager.set_voip_settings(device_id, voip_settings)
        
        if success:
            flash('Configurações VoIP atualizadas com sucesso', 'success')
            
            # Registrar log
            log_entry = LogEntry(
                level='info',
                source=f'TR-069',
                message=f'Configurações VoIP atualizadas para o dispositivo {device_id}'
            )
            db.session.add(log_entry)
            db.session.commit()
        else:
            flash('Erro ao atualizar configurações VoIP', 'danger')
        
        return redirect(url_for('tr069.voip_settings', device_id=device_id))
    
    # Obter configurações VoIP atuais
    voip_settings = tr069_manager.get_voip_settings(device_id)
    
    return render_template('tr069/voip_settings.html', 
                          title=f'Configurações VoIP: {device_id}',
                          device_id=device_id,
                          voip_settings=voip_settings)

@tr069_bp.route('/device/<device_id>/firmware', methods=['GET', 'POST'])
@login_required
def firmware_update(device_id):
    """
    Gerencia atualização de firmware de um dispositivo
    """
    tr069_manager = current_app.config.get('TR069_MANAGER')
    if not tr069_manager:
        flash('Gerenciador TR-069 não está configurado', 'warning')
        return redirect(url_for('tr069.device_details', device_id=device_id))
    
    if request.method == 'POST':
        # Iniciar atualização de firmware
        firmware_url = request.form.get('firmware_url')
        if not firmware_url:
            flash('URL do firmware é obrigatória', 'danger')
            return redirect(url_for('tr069.firmware_update', device_id=device_id))
        
        operation_id = tr069_manager.download(
            device_id=device_id,
            file_type=1,  # 1 = Firmware
            url=firmware_url,
            username=request.form.get('username'),
            password=request.form.get('password'),
            file_size=int(request.form.get('file_size', 0)),
            target_filename=request.form.get('filename')
        )
        
        if operation_id:
            flash('Atualização de firmware iniciada com sucesso', 'success')
            
            # Registrar log
            log_entry = LogEntry(
                level='info',
                source=f'TR-069',
                message=f'Atualização de firmware iniciada para o dispositivo {device_id}'
            )
            db.session.add(log_entry)
            db.session.commit()
        else:
            flash('Erro ao iniciar atualização de firmware', 'danger')
        
        return redirect(url_for('tr069.firmware_update', device_id=device_id))
    
    return render_template('tr069/firmware_update.html', 
                          title=f'Atualização de Firmware: {device_id}',
                          device_id=device_id)

@tr069_bp.route('/device/<device_id>/reboot', methods=['POST'])
@login_required
def reboot_device(device_id):
    """
    Reinicia um dispositivo
    """
    tr069_manager = current_app.config.get('TR069_MANAGER')
    if not tr069_manager:
        flash('Gerenciador TR-069 não está configurado', 'warning')
        return redirect(url_for('tr069.device_details', device_id=device_id))
    
    success = tr069_manager.reboot_device(device_id)
    
    if success:
        flash('Dispositivo reiniciado com sucesso', 'success')
        
        # Registrar log
        log_entry = LogEntry(
            level='info',
            source=f'TR-069',
            message=f'Dispositivo {device_id} reiniciado'
        )
        db.session.add(log_entry)
        db.session.commit()
    else:
        flash('Erro ao reiniciar dispositivo', 'danger')
    
    return redirect(url_for('tr069.device_details', device_id=device_id))

@tr069_bp.route('/device/<device_id>/factory-reset', methods=['POST'])
@login_required
def factory_reset(device_id):
    """
    Restaura as configurações de fábrica de um dispositivo
    """
    tr069_manager = current_app.config.get('TR069_MANAGER')
    if not tr069_manager:
        flash('Gerenciador TR-069 não está configurado', 'warning')
        return redirect(url_for('tr069.device_details', device_id=device_id))
    
    success = tr069_manager.factory_reset(device_id)
    
    if success:
        flash('Configurações de fábrica restauradas com sucesso', 'success')
        
        # Registrar log
        log_entry = LogEntry(
            level='warning',
            source=f'TR-069',
            message=f'Configurações de fábrica restauradas para o dispositivo {device_id}'
        )
        db.session.add(log_entry)
        db.session.commit()
    else:
        flash('Erro ao restaurar configurações de fábrica', 'danger')
    
    return redirect(url_for('tr069.device_details', device_id=device_id))

@tr069_bp.route('/device/<device_id>/diagnostics', methods=['GET', 'POST'])
@login_required
def run_diagnostics(device_id):
    """
    Executa diagnósticos em um dispositivo
    """
    tr069_manager = current_app.config.get('TR069_MANAGER')
    if not tr069_manager:
        flash('Gerenciador TR-069 não está configurado', 'warning')
        return redirect(url_for('tr069.device_details', device_id=device_id))
    
    if request.method == 'POST':
        diagnostic_type = request.form.get('diagnostic_type')
        if not diagnostic_type:
            flash('Tipo de diagnóstico é obrigatório', 'danger')
            return redirect(url_for('tr069.run_diagnostics', device_id=device_id))
        
        results = tr069_manager.run_diagnostics(device_id, diagnostic_type)
        
        if results:
            # Registrar log
            log_entry = LogEntry(
                level='info',
                source=f'TR-069',
                message=f'Diagnóstico {diagnostic_type} executado para o dispositivo {device_id}'
            )
            db.session.add(log_entry)
            db.session.commit()
            
            return render_template('tr069/diagnostic_results.html', 
                                  title=f'Resultados do Diagnóstico: {device_id}',
                                  device_id=device_id,
                                  diagnostic_type=diagnostic_type,
                                  results=results)
        else:
            flash('Erro ao executar diagnóstico', 'danger')
            return redirect(url_for('tr069.run_diagnostics', device_id=device_id))
    
    return render_template('tr069/diagnostics.html', 
                          title=f'Diagnósticos: {device_id}',
                          device_id=device_id)

@tr069_bp.route('/acs/start', methods=['POST'])
@login_required
def start_acs():
    """
    Inicia o servidor ACS
    """
    acs_server = current_app.config.get('TR069_ACS_SERVER')
    if not acs_server:
        # Criar novo servidor ACS
        acs_server = TR069ACSServer(
            listen_host=current_app.config.get('TR069_ACS_HOST', '0.0.0.0'),
            listen_port=current_app.config.get('TR069_ACS_PORT', 7547),
            username=current_app.config.get('TR069_ACS_USERNAME'),
            password=current_app.config.get('TR069_ACS_PASSWORD')
        )
        current_app.config['TR069_ACS_SERVER'] = acs_server
    
    success = acs_server.start()
    
    if success:
        flash('Servidor ACS iniciado com sucesso', 'success')
        
        # Registrar log
        log_entry = LogEntry(
            level='info',
            source='Sistema',
            message='Servidor ACS iniciado'
        )
        db.session.add(log_entry)
        db.session.commit()
    else:
        flash('Erro ao iniciar servidor ACS', 'danger')
    
    return redirect(url_for('tr069.dashboard'))

@tr069_bp.route('/acs/stop', methods=['POST'])
@login_required
def stop_acs():
    """
    Para o servidor ACS
    """
    acs_server = current_app.config.get('TR069_ACS_SERVER')
    if not acs_server:
        flash('Servidor ACS não está configurado', 'warning')
        return redirect(url_for('tr069.dashboard'))
    
    success = acs_server.stop()
    
    if success:
        flash('Servidor ACS parado com sucesso', 'success')
        
        # Registrar log
        log_entry = LogEntry(
            level='info',
            source='Sistema',
            message='Servidor ACS parado'
        )
        db.session.add(log_entry)
        db.session.commit()
    else:
        flash('Erro ao parar servidor ACS', 'danger')
    
    return redirect(url_for('tr069.dashboard'))

@tr069_bp.route('/acs/settings', methods=['GET', 'POST'])
@login_required
def acs_settings():
    """
    Configura o servidor ACS
    """
    if request.method == 'POST':
        # Atualizar configurações do ACS
        current_app.config['TR069_ACS_HOST'] = request.form.get('host', '0.0.0.0')
        current_app.config['TR069_ACS_PORT'] = int(request.form.get('port', 7547))
        current_app.config['TR069_ACS_USERNAME'] = request.form.get('username')
        current_app.config['TR069_ACS_PASSWORD'] = request.form.get('password')
        
        # Atualizar URL do ACS para o gerenciador TR-069
        tr069_manager = current_app.config.get('TR069_MANAGER')
        if not tr069_manager:
            tr069_manager = TR069Manager(
                acs_url=f"http://{current_app.config['TR069_ACS_HOST']}:{current_app.config['TR069_ACS_PORT']}",
                username=current_app.config['TR069_ACS_USERNAME'],
                password=current_app.config['TR069_ACS_PASSWORD']
            )
            current_app.config['TR069_MANAGER'] = tr069_manager
        
        flash('Configurações do ACS atualizadas com sucesso', 'success')
        return redirect(url_for('tr069.dashboard'))
    
    return render_template('tr069/acs_settings.html', 
                          title='Configurações do ACS',
                          host=current_app.config.get('TR069_ACS_HOST', '0.0.0.0'),
                          port=current_app.config.get('TR069_ACS_PORT', 7547),
                          username=current_app.config.get('TR069_ACS_USERNAME', ''),
                          password=current_app.config.get('TR069_ACS_PASSWORD', ''))
