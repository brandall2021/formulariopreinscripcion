URL_PORTAL = "https://inscripciones.face.unt.edu.ar"

def plantilla_observaciones(nombre: str, numero: str,
                            observaciones: list[dict]) -> tuple[str, str]:
    items = "\n".join(f"{i}. {o.get('nombre', o['documento_id'])}: {o['motivo']}"
                      for i, o in enumerate(observaciones, 1))
    asunto = "Observaciones en su documentación – Preinscripción FACE"
    cuerpo = (f"Estimado/a {nombre}:\n\nDurante la revisión de su documentación "
              f"correspondiente a la preinscripción en FACE se detectaron las "
              f"siguientes observaciones:\n{items}\n\nPara subsanarlas ingrese a "
              f"{URL_PORTAL}.\nSolicitud: {numero}.\n\nDepartamento de Alumnos – FACE")
    return asunto, cuerpo

def plantilla_aprobada(nombre: str, numero: str) -> tuple[str, str]:
    asunto = "Documentación aprobada – Preinscripción FACE"
    cuerpo = (f"Estimado/a {nombre}:\n\nSu documentación de la solicitud {numero} "
              f"fue aprobada. Puede continuar el trámite administrativo en {URL_PORTAL}.\n\n"
              f"Departamento de Alumnos – FACE")
    return asunto, cuerpo
