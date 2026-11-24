import uuid

from pydantic import BaseModel, ConfigDict, Field, computed_field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class CambioContrasenaRequest(BaseModel):
    actual: str = Field(min_length=1, max_length=255)
    nueva: str = Field(min_length=1, max_length=255)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    rol: str
    zona_id: uuid.UUID | None = None
    # ADR-0019: nombre (solo tiene valor para roles sin tabla propia: coordinador/admin/auditor).
    nombres: str | None = None
    apellidos: str | None = None
    # `foto_ref` nunca se expone (es una ruta de archivo cifrado interna); solo se informa si hay
    # foto cargada. El contenido se consulta aparte, en `GET /auth/yo/foto`.
    foto_ref: str | None = Field(default=None, exclude=True, repr=False)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tiene_foto(self) -> bool:
        return bool(self.foto_ref)


class UsuarioAutoUpdate(BaseModel):
    """Solo para roles sin tabla propia (coordinador/admin/auditor): madre y profesional/defensor
    ya tienen su nombre en su propia tabla (ADR-0019)."""

    nombres: str | None = Field(default=None, min_length=1, max_length=120)
    apellidos: str | None = Field(default=None, min_length=1, max_length=120)
