import sys
import os

script = os.path.join(os.path.dirname(__file__), 'core', 'main.py')

# Executa o script principal diretamente no mesmo processo
with open(script) as f:
    code = compile(f.read(), script, 'exec')
    exec(code)
