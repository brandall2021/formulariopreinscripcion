ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "BORRADOR": {"RECIBIDA", "RECHAZADA"},
    "RECIBIDA": {"EN_VALIDACION", "RECHAZADA"},
    "EN_VALIDACION": {"EN_AUDITORIA", "RECHAZADA"},
    "EN_AUDITORIA": {"DOCUMENTACION_APROBADA", "OBSERVADA", "RECHAZADA"},
    "OBSERVADA": {"PENDIENTE_ALUMNO", "RECHAZADA"},
    "PENDIENTE_ALUMNO": {"REENVIADA", "RECHAZADA"},
    "REENVIADA": {"EN_REAUDITORIA", "RECHAZADA"},
    "EN_REAUDITORIA": {"DOCUMENTACION_APROBADA", "OBSERVADA", "RECHAZADA"},
    "DOCUMENTACION_APROBADA": {"FINALIZADA", "RECHAZADA"},
    "FINALIZADA": set(),
    "RECHAZADA": set(),
}

class InvalidTransition(Exception):
    pass

def transition(actual: str, nuevo: str) -> str:
    if nuevo not in ALLOWED_TRANSITIONS.get(actual, set()):
        raise InvalidTransition(f"{actual} -> {nuevo}")
    return nuevo
