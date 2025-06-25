# core/engine_boot.py

import subprocess
import os
import signal
import atexit
import sys
import psutil
import time
import logging

ENGINE_PROCESS = None
ENGINE_PORT = 50051
logger = logging.getLogger(__name__)

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

def _collect_engine_pids() -> list[int]:
    """Devolve todos os PIDs que escutam a porta da engine (50051)."""
    pids = []
    for proc in psutil.process_iter(['pid']):
        try:
            for con in proc.connections(kind='inet'):
                if con.laddr.port == ENGINE_PORT:
                    pids.append(proc.pid)
                    break
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return pids


def _kill_pid(pid: int) -> None:
    """Tenta terminar o processo com SIGTERM; se não morrer → SIGKILL."""
    try:
        p = psutil.Process(pid)
        if os.name == 'nt':
            p.send_signal(signal.SIGTERM)
        else:
            p.terminate()
        p.wait(timeout=3)
    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
        try:                         # força
            p.kill()
        except Exception:
            pass


def launch_engine():
    """
    • Se existirem instâncias órfãs (GUI anterior crashou) → mata todas.
    • Depois inicia uma nova engine.go e aguarda escuta da porta.
    """
    global ENGINE_PROCESS

    # 1️⃣  varre porta 50051
    stale_pids = _collect_engine_pids()
    if stale_pids:
        logger.info("Encontradas instâncias órfãs: %s – encerrando…", stale_pids)
        for pid in stale_pids:
            if pid != os.getpid():   # nunca mate o próprio Python
                _kill_pid(pid)

    # 2️⃣  agora deve estar livre
    if _collect_engine_pids():
        logger.error("Falha: porta 50051 continua ocupada.")
        raise RuntimeError("Não foi possível liberar a porta 50051.")

    # 3️⃣  inicia engine fresca
    go_dir = os.path.join(os.getcwd(), "ping_engine", "go")
    logger.info("Iniciando engine.go via subprocess…")

    ENGINE_PROCESS = subprocess.Popen(
        ["go", "run", "engine.go"],
        cwd=go_dir,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # 4️⃣  espera até a porta responder (máximo 5 s)
    for _ in range(50):
        if _collect_engine_pids():
            logger.info("Engine iniciada com sucesso.")
            return
        time.sleep(0.1)

    logger.error("Falha: a engine não iniciou a tempo.")
    try:
        out, err = ENGINE_PROCESS.communicate(timeout=5)
        if out:
            logger.error("ENGINE OUTPUT %s", out)
        if err:
            logger.error("ENGINE ERRO %s", err)
    except Exception:
        pass
    raise RuntimeError("Engine.go não pôde ser iniciada.")

def shutdown_engine():
    """
    Encerra a engine Go se ela foi iniciada por este processo.
    """
    global ENGINE_PROCESS
    if ENGINE_PROCESS and ENGINE_PROCESS.poll() is None:
        logger.info("Encerrando engine.go…")
        if os.name == 'nt':
            ENGINE_PROCESS.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            ENGINE_PROCESS.terminate()
        ENGINE_PROCESS.wait(timeout=5)
        logger.info("Engine finalizada.")

# Registro de saída segura
atexit.register(shutdown_engine)

if os.name != 'nt':
    import signal
    signal.signal(signal.SIGTERM, lambda *_: shutdown_engine())
    signal.signal(signal.SIGINT, lambda *_: shutdown_engine())
