from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models.models import OLT, ONU, LogEntry
from app.models.snmp_manager import SNMPManager, HuaweiOLTManager
from app import db
import datetime

onu_bp = Blueprint('onu', __name__)

@onu_bp.route('/list')
@login_required
def list_onus():
    """
    Lista todas as ONUs cadastradas
    """
    onus = ONU.query.all()
    olts = OLT.query.all()
    return render_template('onu/list.html', title='ONUs', onus=onus, olts=olts)

@onu_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_onu():
    """
    Adiciona uma nova ONU manualmente
    """
    olts = OLT.query.all()
    
    if request.method == 'POST':
        serial_number = request.form.get('serial_number')
        name = request.form.get('name')
        olt_id = int(request.form.get('olt_id'))
        port = request.form.get('port')
        
        # Verificar se já existe uma ONU com este serial
        existing_onu = ONU.query.filter_by(serial_number=serial_number).first()
        if existing_onu:
            flash('Já existe uma ONU cadastrada com este número de série', 'danger')
            return redirect(url_for('onu.add_onu'))
        
        # Criar nova ONU
        onu = ONU(
            serial_number=serial_number,
            name=name,
            olt_id=olt_id,
            port=port,
            status='unknown',
            created_at=datetime.datetime.utcnow()
        )
        
        db.session.add(onu)
        
        # Registrar log
        log_entry = LogEntry(
            level='info',
            source='Sistema',
            message=f'Nova ONU adicionada manualmente: {name} ({serial_number})'
        )
        db.session.add(log_entry)
        
        db.session.commit()
        
        flash('ONU adicionada com sucesso', 'success')
        return redirect(url_for('onu.list_onus'))
    
    return render_template('onu/add.html', title='Adicionar ONU', olts=olts)

@onu_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_onu(id):
    """
    Edita uma ONU existente
    """
    onu = ONU.query.get_or_404(id)
    olts = OLT.query.all()
    
    if request.method == 'POST':
        onu.name = request.form.get('name')
        onu.olt_id = int(request.form.get('olt_id'))
        onu.port = request.form.get('port')
        
        # Registrar log
        log_entry = LogEntry(
            level='info',
            source='Sistema',
            message=f'ONU editada: {onu.name} ({onu.serial_number})'
        )
        db.session.add(log_entry)
        
        db.session.commit()
        
        flash('ONU atualizada com sucesso', 'success')
        return redirect(url_for('onu.list_onus'))
    
    return render_template('onu/edit.html', title='Editar ONU', onu=onu, olts=olts)

@onu_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_onu(id):
    """
    Remove uma ONU
    """
    onu = ONU.query.get_or_404(id)
    
    # Registrar log
    log_entry = LogEntry(
        level='warning',
        source='Sistema',
        message=f'ONU removida: {onu.name} ({onu.serial_number})'
    )
    db.session.add(log_entry)
    
    # Remover ONU
    db.session.delete(onu)
    db.session.commit()
    
    flash('ONU removida com sucesso', 'success')
    return redirect(url_for('onu.list_onus'))

@onu_bp.route('/details/<int:id>')
@login_required
def onu_details(id):
    """
    Exibe detalhes de uma ONU específica
    """
    onu = ONU.query.get_or_404(id)
    olt = OLT.query.get(onu.olt_id)
    
    return render_template('onu/details.html', 
                          title=f'ONU: {onu.name}',
                          onu=onu,
                          olt=olt)

@onu_bp.route('/enable/<int:id>')
@login_required
def enable_onu(id):
    """
    Habilita uma ONU específica
    """
    onu = ONU.query.get_or_404(id)
    olt = OLT.query.get(onu.olt_id)
    
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
        
        # Extrair ID da ONU (pode variar dependendo da implementação)
        onu_id = onu.port.split('/')[-1] if '/' in onu.port else '1'
        
        # Habilitar ONU
        success, err = huawei_manager.enable_onu(onu_id)
        
        if success:
            onu.status = 'online'
            
            log_entry = LogEntry(
                level='info',
                source=f'OLT {olt.name}',
                message=f'ONU habilitada: {onu.name} ({onu.serial_number})'
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash('ONU habilitada com sucesso', 'success')
        else:
            flash(f'Erro ao habilitar ONU: {err}', 'danger')
            
            log_entry = LogEntry(
                level='error',
                source=f'OLT {olt.name}',
                message=f'Erro ao habilitar ONU {onu.name}: {err}'
            )
            db.session.add(log_entry)
            db.session.commit()
        
    except Exception as e:
        flash(f'Erro ao habilitar ONU: {str(e)}', 'danger')
        
        log_entry = LogEntry(
            level='error',
            source=f'OLT {olt.name}',
            message=f'Erro ao habilitar ONU {onu.name}: {str(e)}'
        )
        db.session.add(log_entry)
        db.session.commit()
    
    return redirect(url_for('onu.onu_details', id=id))

@onu_bp.route('/disable/<int:id>')
@login_required
def disable_onu(id):
    """
    Desabilita uma ONU específica
    """
    onu = ONU.query.get_or_404(id)
    olt = OLT.query.get(onu.olt_id)
    
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
        
        # Extrair ID da ONU (pode variar dependendo da implementação)
        onu_id = onu.port.split('/')[-1] if '/' in onu.port else '1'
        
        # Desabilitar ONU
        success, err = huawei_manager.disable_onu(onu_id)
        
        if success:
            onu.status = 'disabled'
            
            log_entry = LogEntry(
                level='info',
                source=f'OLT {olt.name}',
                message=f'ONU desabilitada: {onu.name} ({onu.serial_number})'
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash('ONU desabilitada com sucesso', 'success')
        else:
            flash(f'Erro ao desabilitar ONU: {err}', 'danger')
            
            log_entry = LogEntry(
                level='error',
                source=f'OLT {olt.name}',
                message=f'Erro ao desabilitar ONU {onu.name}: {err}'
            )
            db.session.add(log_entry)
            db.session.commit()
        
    except Exception as e:
        flash(f'Erro ao desabilitar ONU: {str(e)}', 'danger')
        
        log_entry = LogEntry(
            level='error',
            source=f'OLT {olt.name}',
            message=f'Erro ao desabilitar ONU {onu.name}: {str(e)}'
        )
        db.session.add(log_entry)
        db.session.commit()
    
    return redirect(url_for('onu.onu_details', id=id))

@onu_bp.route('/refresh/<int:id>')
@login_required
def refresh_onu(id):
    """
    Atualiza os dados de uma ONU específica via SNMP
    """
    onu = ONU.query.get_or_404(id)
    olt = OLT.query.get(onu.olt_id)
    
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
        
        # Extrair ID da ONU (pode variar dependendo da implementação)
        onu_id = onu.port.split('/')[-1] if '/' in onu.port else '1'
        
        # Obter status da ONU
        status, err = huawei_manager.get_onu_status(onu_id)
        if err:
            flash(f'Erro ao obter status da ONU: {err}', 'danger')
        else:
            onu.status = status
        
        # Obter nível de sinal da ONU
        signal, err = huawei_manager.get_onu_signal(onu_id)
        if err:
            flash(f'Erro ao obter nível de sinal da ONU: {err}', 'danger')
        else:
            onu.signal_strength = signal
        
        onu.last_seen = datetime.datetime.utcnow()
        db.session.commit()
        
        flash('Dados da ONU atualizados com sucesso', 'success')
        
    except Exception as e:
        flash(f'Erro ao atualizar dados da ONU: {str(e)}', 'danger')
        
        log_entry = LogEntry(
            level='error',
            source=f'OLT {olt.name}',
            message=f'Erro ao atualizar dados da ONU {onu.name}: {str(e)}'
        )
        db.session.add(log_entry)
        db.session.commit()
    
    return redirect(url_for('onu.onu_details', id=id))
