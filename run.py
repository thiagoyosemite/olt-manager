from app import create_app, db
from app.models.models import User
import os
import click
from flask.cli import with_appcontext

app = create_app()

@app.cli.command("create-admin")
@click.option('--username', default='admin', help='Nome de usuário do administrador')
@click.option('--email', default='admin@example.com', help='Email do administrador')
@click.option('--password', help='Senha do administrador')
@with_appcontext
def create_admin(username, email, password):
    """Cria um usuário administrador."""
    if not password:
        password = click.prompt('Digite a senha para o administrador', hide_input=True, confirmation_prompt=True)
    
    user = User.query.filter_by(username=username).first()
    if user:
        click.echo(f'Usuário {username} já existe.')
        return
    
    user = User(username=username, email=email, is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f'Usuário administrador {username} criado com sucesso.')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
