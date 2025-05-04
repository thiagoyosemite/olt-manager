from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.models.models import OLT, ONU, LogEntry
from app.models.snmp_manager import SNMPManager, HuaweiOLTManager
from app import db
import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/index')
@login_required
def index():
    """
    Página inicial do dashboard
    """
    # Obter informações básicas para o dashboard
    olts = OLT.query.all()
    total_olts = len(olts)
    
    total_onus = ONU.query.count()
    online_onus = ONU.query.filter_by(status='online').count()
    offline_onus = ONU.query.filter_by(status='offline').count()
    
    # Obter logs recentes
    recent_logs = LogEntry.query.order_by(LogEntry.timestamp.desc()).limit(10).all()
    
    return render_template('index.html', 
                          title='Dashboard',
                          total_olts=total_olts,
                          total_onus=total_onus,
                          online_onus=online_onus,
                          offline_onus=offline_onus,
                          recent_logs=recent_logs,
                          olts=olts)

@main_bp.route('/about')
def about():
    """
    Página sobre o sistema
    """
    return render_template('about.html', title='Sobre')

@main_bp.route('/refresh_data')
@login_required
def refresh_data():
    """
    Atualiza os dados de todas as OLTs e ONUs via SNMP
    """
    olts = OLT.query.all()
    
    for olt in olts:
        try:
            # Criar gerenciador SNMP para a OLT
            snmp_manager = SNMPManager(
                host=olt.ip_address,
                community=olt.snmp_community,
                port=olt.snmp_port,
                version=olt.snmp_version
            )
            
            # Criar gerenciador específico para Huawei
            huawei_manager = HuaweiOLTManager(snmp_manager)
            
            # Obter informações do sistema
            system_info, err = huawei_manager.get_system_info()
            if err:
                log_entry = LogEntry(
                    level='error',
                    source=f'OLT {olt.name}',
                    message=f'Erro ao obter informações do sistema: {err}'
                )
                db.session.add(log_entry)
                continue
            
            # Atualizar status da OLT
            olt.status = 'online'
            olt.last_check = datetime.datetime.utcnow()
            
            # Obter lista de ONUs
            onu_list, err = huawei_manager.get_onu_list()
            if err:
                log_entry = LogEntry(
                    level='error',
                    source=f'OLT {olt.name}',
                    message=f'Erro ao obter lista de ONUs: {err}'
                )
                db.session.add(log_entry)
                continue
            
            # Atualizar informações das ONUs
            for onu_info in onu_list:
                onu = ONU.query.filter_by(serial_number=onu_info['serial'], olt_id=olt.id).first()
                
                if not onu:
                    # Nova ONU encontrada
                    onu = ONU(
                        serial_number=onu_info['serial'],
                        name=f'ONU-{onu_info["id"]}',
                        olt_id=olt.id,
                        port=onu_info.get('port', 'unknown'),
                        status='unknown',
                        created_at=datetime.datetime.utcnow()
                    )
                    db.session.add(onu)
                    
                    log_entry = LogEntry(
                        level='info',
                        source=f'OLT {olt.name}',
                        message=f'Nova ONU detectada: {onu_info["serial"]}'
                    )
                    db.session.add(log_entry)
                
                # Obter status da ONU
                status, err = huawei_manager.get_onu_status(onu_info['id'])
                if not err:
                    onu.status = status
                
                # Obter nível de sinal da ONU
                signal, err = huawei_manager.get_onu_signal(onu_info['id'])
                if not err:
                    onu.signal_strength = signal
                
                onu.last_seen = datetime.datetime.utcnow()
            
            db.session.commit()
            
            log_entry = LogEntry(
                level='info',
                source=f'OLT {olt.name}',
                message=f'Dados atualizados com sucesso. {len(onu_list)} ONUs encontradas.'
            )
            db.session.add(log_entry)
            
        except Exception as e:
            log_entry = LogEntry(
                level='error',
                source=f'OLT {olt.name}',
                message=f'Erro ao atualizar dados: {str(e)}'
            )
            db.session.add(log_entry)
            
            olt.status = 'error'
            olt.last_check = datetime.datetime.utcnow()
            
        finally:
            db.session.commit()
    
    flash('Dados atualizados com sucesso', 'success')
    return redirect(url_for('main.index'))
