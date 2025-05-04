from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models.models import OLT, ONU, LogEntry
from app.models.snmp_manager import SNMPManager, HuaweiOLTManager
from app import db
import datetime

olt_bp = Blueprint('olt', __name__)

@olt_bp.route('/list')
@login_required
def list_olts():
    """
    Lista todas as OLTs cadastradas
    """
    olts = OLT.query.all()
    return render_template('olt/list.html', title='OLTs', olts=olts)

@olt_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_olt():
    """
    Adiciona uma nova OLT
    """
    if request.method == 'POST':
        name = request.form.get('name')
        ip_address = request.form.get('ip_address')
        model = request.form.get('model', 'MA5800-X7')
        vendor = request.form.get('vendor', 'Huawei')
        snmp_community = request.form.get('snmp_community')
        snmp_version = request.form.get('snmp_version', '2c')
        snmp_port = int(request.form.get('snmp_port', 161))
        
        # Verificar se já existe uma OLT com este IP
        existing_olt = OLT.query.filter_by(ip_address=ip_address).first()
        if existing_olt:
            flash('Já existe uma OLT cadastrada com este endereço IP', 'danger')
            return redirect(url_for('olt.add_olt'))
        
        # Criar nova OLT
        olt = OLT(
            name=name,
            ip_address=ip_address,
            model=model,
            vendor=vendor,
            snmp_community=snmp_community,
            snmp_version=snmp_version,
            snmp_port=snmp_port,
            status='unknown',
            created_at=datetime.datetime.utcnow()
        )
        
        db.session.add(olt)
        
        # Registrar log
        log_entry = LogEntry(
            level='info',
            source='Sistema',
            message=f'Nova OLT adicionada: {name} ({ip_address})'
        )
        db.session.add(log_entry)
        
        db.session.commit()
        
        flash('OLT adicionada com sucesso', 'success')
        return redirect(url_for('olt.list_olts'))
    
    return render_template('olt/add.html', title='Adicionar OLT')

@olt_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_olt(id):
    """
    Edita uma OLT existente
    """
    olt = OLT.query.get_or_404(id)
    
    if request.method == 'POST':
        olt.name = request.form.get('name')
        olt.ip_address = request.form.get('ip_address')
        olt.model = request.form.get('model')
        olt.vendor = request.form.get('vendor')
        olt.snmp_community = request.form.get('snmp_community')
        olt.snmp_version = request.form.get('snmp_version')
        olt.snmp_port = int(request.form.get('snmp_port', 161))
        
        # Registrar log
        log_entry = LogEntry(
            level='info',
            source='Sistema',
            message=f'OLT editada: {olt.name} ({olt.ip_address})'
        )
        db.session.add(log_entry)
        
        db.session.commit()
        
        flash('OLT atualizada com sucesso', 'success')
        return redirect(url_for('olt.list_olts'))
    
    return render_template('olt/edit.html', title='Editar OLT', olt=olt)

@olt_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_olt(id):
    """
    Remove uma OLT
    """
    olt = OLT.query.get_or_404(id)
    
    # Registrar log
    log_entry = LogEntry(
        level='warning',
        source='Sistema',
        message=f'OLT removida: {olt.name} ({olt.ip_address})'
    )
    db.session.add(log_entry)
    
    # Remover ONUs associadas
    ONU.query.filter_by(olt_id=id).delete()
    
    # Remover OLT
    db.session.delete(olt)
    db.session.commit()
    
    flash('OLT removida com sucesso', 'success')
    return redirect(url_for('olt.list_olts'))

@olt_bp.route('/details/<int:id>')
@login_required
def olt_details(id):
    """
    Exibe detalhes de uma OLT específica
    """
    olt = OLT.query.get_or_404(id)
    onus = ONU.query.filter_by(olt_id=id).all()
    
    # Estatísticas
    total_onus = len(onus)
    online_onus = sum(1 for onu in onus if onu.status == 'online')
    offline_onus = sum(1 for onu in onus if onu.status == 'offline')
    
    return render_template('olt/details.html', 
                          title=f'OLT: {olt.name}',
                          olt=olt,
                          onus=onus,
                          total_onus=total_onus,
                          online_onus=online_onus,
                          offline_onus=offline_onus)

@olt_bp.route('/refresh/<int:id>')
@login_required
def refresh_olt(id):
    """
    Atualiza os dados de uma OLT específica via SNMP
    """
    olt = OLT.query.get_or_404(id)
    
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
            flash(f'Erro ao obter informações do sistema: {err}', 'danger')
            
            log_entry = LogEntry(
                level='error',
                source=f'OLT {olt.name}',
                message=f'Erro ao obter informações do sistema: {err}'
            )
            db.session.add(log_entry)
            db.session.commit()
            
            return redirect(url_for('olt.olt_details', id=id))
        
        # Atualizar status da OLT
        olt.status = 'online'
        olt.last_check = datetime.datetime.utcnow()
        
        # Obter lista de ONUs
        onu_list, err = huawei_manager.get_onu_list()
        if err:
            flash(f'Erro ao obter lista de ONUs: {err}', 'danger')
            
            log_entry = LogEntry(
                level='error',
                source=f'OLT {olt.name}',
                message=f'Erro ao obter lista de ONUs: {err}'
            )
            db.session.add(log_entry)
            db.session.commit()
            
            return redirect(url_for('olt.olt_details', id=id))
        
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
        db.session.commit()
        
        flash('Dados da OLT atualizados com sucesso', 'success')
        
    except Exception as e:
        flash(f'Erro ao atualizar dados da OLT: {str(e)}', 'danger')
        
        log_entry = LogEntry(
            level='error',
            source=f'OLT {olt.name}',
            message=f'Erro ao atualizar dados: {str(e)}'
        )
        db.session.add(log_entry)
        
        olt.status = 'error'
        olt.last_check = datetime.datetime.utcnow()
        db.session.commit()
    
    return redirect(url_for('olt.olt_details', id=id))
