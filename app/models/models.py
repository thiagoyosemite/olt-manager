from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

class OLT(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True)
    ip_address = db.Column(db.String(15), unique=True)
    model = db.Column(db.String(64))
    vendor = db.Column(db.String(64))
    snmp_community = db.Column(db.String(64))
    snmp_version = db.Column(db.String(8))
    snmp_port = db.Column(db.Integer, default=161)
    status = db.Column(db.String(16), default='unknown')
    last_check = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    onus = db.relationship('ONU', backref='olt', lazy='dynamic')
    
    def __repr__(self):
        return f'<OLT {self.name} ({self.ip_address})>'

class ONU(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(32), index=True, unique=True)
    name = db.Column(db.String(64))
    olt_id = db.Column(db.Integer, db.ForeignKey('olt.id'))
    port = db.Column(db.String(32))
    status = db.Column(db.String(16), default='unknown')
    signal_strength = db.Column(db.Float)
    mac_address = db.Column(db.String(17))
    ip_address = db.Column(db.String(15))
    model = db.Column(db.String(64))
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ONU {self.serial_number} ({self.name})>'

class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(16))
    source = db.Column(db.String(32))
    message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Log {self.timestamp}: {self.message[:30]}...>'
