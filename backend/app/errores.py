"""Errores de negocio con su codigo HTTP."""


class ErrorNegocio(Exception):
    """Error esperado (saldo insuficiente, cuenta inexistente...).

    Se convierte en una respuesta JSON con el codigo HTTP indicado.
    """

    def __init__(self, codigo_http: int, mensaje: str):
        super().__init__(mensaje)
        self.codigo_http = codigo_http
        self.mensaje = mensaje
