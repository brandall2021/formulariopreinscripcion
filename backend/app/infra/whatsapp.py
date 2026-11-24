import json
from pathlib import Path
from datetime import datetime

class WhatsAppMock:
    def __init__(self, path: str = "var/whatsapp-mock.log"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def send(self, to: str, body: str) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"fecha": datetime.utcnow().isoformat(),
                                 "para": to, "cuerpo": body}, ensure_ascii=False) + "\n")
