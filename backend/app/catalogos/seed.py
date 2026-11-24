from sqlalchemy.orm import Session
from app.catalogos.models import Carrera, Convocatoria, RequisitoDocumental, TipoDocumento

TIPOS = [
    ("dni", "DNI", "Frente y dorso, color y legible"),
    ("foto_carnet", "Foto carnet", "Fondo claro, frente y perfil derecho"),
    ("acta_nacimiento", "Acta de nacimiento", "Actualizada, legalizada y de ambos lados"),
    ("titulo_secundario", "Título secundario", "Título o constancia sin materias adeudadas"),
    ("formulario_siu", "Formulario SIU Guaraní", "Formulario de preinscripción obtenido de SIU"),
    ("comprobante_pago", "Comprobante de pago", "Imagen o PDF legible"),
]
CARRERAS = [("Contador Público", "CP"), ("Economía", "ECO"), ("Administración", "ADM")]

def seed_catalogos(db: Session) -> None:
    # El guard es específico de la convocatoria semilla: si ya existe otra
    # convocatoria (p. ej. de otro año), igual debemos cargar catálogos.
    if db.query(Convocatoria).filter_by(nombre="Convocatoria 2026").first() is not None:
        return
    conv = Convocatoria(nombre="Convocatoria 2026", anio=2026, activa=True)
    db.add(conv)
    db.flush()
    tipos = [TipoDocumento(codigo=c, nombre=n, descripcion=d) for c, n, d in TIPOS]
    carreras = [Carrera(nombre=n, codigo=c, activa=True) for n, c in CARRERAS]
    db.add_all(tipos + carreras)
    db.flush()
    db.add_all(RequisitoDocumental(
        convocatoria_id=conv.id, carrera_id=car.id,
        tipo_ingresante="nuevo", tipo_documento_id=td.id, obligatorio=True,
    ) for car in carreras for td in tipos)
    db.commit()
