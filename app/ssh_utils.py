# -*- coding: utf-8 -*-
"""Utilitários para interação SSH com a OLT."""

import paramiko
import time
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLT_HOST = os.getenv("OLT_HOST")
OLT_SSH_PORT = int(os.getenv("OLT_SSH_PORT", 22))
OLT_SSH_USER = os.getenv("OLT_SSH_USER")
OLT_SSH_PASS = os.getenv("OLT_SSH_PASS")

def execute_olt_command(command, expect_prompt=True):
    """Conecta à OLT via SSH, executa um comando e retorna a saída."""
    output = ""
    error = None
    ssh = None
    channel = None

    if not all([OLT_HOST, OLT_SSH_USER, OLT_SSH_PASS]):
        logger.error("Credenciais SSH da OLT não configuradas no .env")
        return None, "Erro: Credenciais SSH da OLT não configuradas."

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        logger.info(f"Conectando a {OLT_HOST}:{OLT_SSH_PORT} com usuário {OLT_SSH_USER}")
        ssh.connect(OLT_HOST, port=OLT_SSH_PORT, username=OLT_SSH_USER, password=OLT_SSH_PASS, timeout=10)
        logger.info("Conexão SSH estabelecida.")

        channel = ssh.invoke_shell()
        logger.info("Shell invocado.")

        # Esperar pelo prompt inicial
        time.sleep(1)
        initial_output = channel.recv(65535).decode("utf-8", errors='ignore')
        logger.debug(f"Saída inicial: {initial_output}")
        output += initial_output

        # Desabilitar paginação (comando comum em Huawei)
        disable_paging_cmd = "scroll"
        logger.info(f"Enviando comando: {disable_paging_cmd}")
        channel.send(disable_paging_cmd + "\n")
        time.sleep(1) # Espera para o comando ser processado
        paging_output = channel.recv(65535).decode("utf-8", errors='ignore')
        logger.debug(f"Saída do comando scroll: {paging_output}")
        output += paging_output

        # Enviar o comando principal
        logger.info(f"Enviando comando: {command}")
        channel.send(command + "\n")

        # Ler a saída até que o prompt apareça novamente (ou um timeout)
        end_time = time.time() + 15 # Timeout de 15 segundos para o comando
        prompt_found = False
        while time.time() < end_time:
            if channel.recv_ready():
                chunk = channel.recv(65535).decode("utf-8", errors='ignore')
                logger.debug(f"Chunk recebido: {chunk}")
                output += chunk
                # Verificar se o prompt esperado está na saída (ajustar conforme necessário)
                # Exemplo: prompt Huawei pode terminar com > ou #
                if expect_prompt and (chunk.strip().endswith(">") or chunk.strip().endswith("#")):
                    logger.info("Prompt encontrado.")
                    prompt_found = True
                    break
            time.sleep(0.5)

        if expect_prompt and not prompt_found:
             logger.warning("Prompt não encontrado após execução do comando.")
             # Pode ser normal para alguns comandos, mas logar como aviso

        logger.info("Comando executado.")

    except paramiko.AuthenticationException:
        logger.error("Falha na autenticação SSH.")
        error = "Erro: Falha na autenticação SSH."
    except paramiko.SSHException as ssh_ex:
        logger.error(f"Erro na conexão SSH: {ssh_ex}")
        error = f"Erro: Problema na conexão SSH ({ssh_ex})."
    except Exception as e:
        logger.error(f"Erro inesperado ao executar comando SSH: {e}")
        error = f"Erro inesperado: {e}"
    finally:
        if channel:
            channel.close()
            logger.info("Canal SSH fechado.")
        if ssh:
            ssh.close()
            logger.info("Conexão SSH fechada.")

    # Limpar a saída removendo ecos de comando e prompts comuns
    lines = output.splitlines()
    cleaned_lines = []
    for line in lines:
        l_strip = line.strip()
        # Remover linhas que são apenas o comando enviado ou prompts comuns
        if l_strip != command and not l_strip.endswith((">")) and not l_strip.endswith(("#")):
             # Adicionar outras condições se necessário para limpar mais a saída
             cleaned_lines.append(line)

    cleaned_output = "\n".join(cleaned_lines).strip()
    logger.debug(f"Saída limpa: {cleaned_output}")

    return cleaned_output, error

# Exemplo de uso (pode ser removido ou comentado)
# if __name__ == '__main__':
#     test_command = "display ont autofind all" # Comando de exemplo
#     result, err = execute_olt_command(test_command)
#     if err:
#         print(f"Erro: {err}")
#     else:
#         print("Resultado:")
#         print(result)

