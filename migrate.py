from core.database import migrate_from_json
from pathlib import Path

json_path = Path(__file__).resolve().parent / "data" / "servers.json"
migrate_from_json(json_path)
print("Migração concluída com sucesso!")
