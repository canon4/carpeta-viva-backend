from fastapi import HTTPException, status


def no_autenticado(detalle: str = "Credenciales inválidas") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detalle, headers={"WWW-Authenticate": "Bearer"})


def prohibido(detalle: str = "No tiene permiso para esta acción") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detalle)


def no_encontrado(detalle: str = "Recurso no encontrado") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detalle)
