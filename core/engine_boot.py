# core/engine_boot.py

import subprocess
import os
import signal
import atexit
import sys
import psutil
import time

ENGINE_PROCESS = None
ENGINE_PORT = 50051

def is_engine_running():
    """
    Verifica se a porta 50051 já está em uso por algum processo.
    """
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == ENGINE_PORT:
                    return True, proc.pid
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return False, None

def launch_engine():
    """
    Inicia a engine Go como subprocesso se não estiver rodando ainda.
    """
    global ENGINE_PROCESS

    running, pid = is_engine_running()
    if running:
        print(f"[ENGINE_BOOT] Engine já está rodando (PID {pid})")
        return

    go_dir = os.path.join(os.getcwd(), "ping_engine", "go")
    print("[ENGINE_BOOT] Iniciando engine.go via subprocess...")

    ENGINE_PROCESS = subprocess.Popen(
        ["go", "run", "engine.go"],
        cwd=go_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Aguarda até a porta estar escutando (máximo 5 segundos)
    for _ in range(50):
        if is_engine_running()[0]:
            print("[ENGINE_BOOT] Engine iniciada com sucesso.")
            return
        time.sleep(0.1)

    # Se chegou aqui, a engine não subiu — exibe erros
    print("[ENGINE_BOOT] Falha: a engine não iniciou a tempo.")
    try:
        stdout, stderr = ENGINE_PROCESS.communicate(timeout=5)
        if stdout:
            print("[ENGINE OUTPUT]", stdout)
        if stderr:
            print("[ENGINE ERRO]", stderr)
    except Exception as e:
        print(f"[ENGINE_BOOT] Erro ao tentar capturar logs da engine: {e}")

def shutdown_engine():
    """
    Encerra a engine Go se ela foi iniciada por este processo.
    """
    global ENGINE_PROCESS
    if ENGINE_PROCESS and ENGINE_PROCESS.poll() is None:
        print("[ENGINE_BOOT] Encerrando engine.go...")
        if os.name == 'nt':
            ENGINE_PROCESS.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            ENGINE_PROCESS.terminate()
        ENGINE_PROCESS.wait(timeout=5)
        print("[ENGINE_BOOT] Engine finalizada.")

# Registro de saída segura
atexit.register(shutdown_engine)

if os.name != 'nt':
    import signal
    signal.signal(signal.SIGTERM, lambda *_: shutdown_engine())
    signal.signal(signal.SIGINT, lambda *_: shutdown_engine())
