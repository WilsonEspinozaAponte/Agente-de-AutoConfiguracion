import yaml

def _validate_and_set_defaults(config: dict):
    """
    Valida la sección 'health_check' y establece valores por defecto
    Modifica el diccionario 'config' in-place
    Lanza ValueError si la configuración es inválida
    """
    if 'services' not in config:
        return # No hay servicios que validar

    for service_name, service_config in config.get('services', {}).items():
        # Continuar solo si el servicio define un health_check
        if 'health_check' in service_config:
            hc_config = service_config['health_check']
            
            if 'type' not in hc_config:
                raise ValueError(f"Servicio '{service_name}': 'health_check' debe definir un 'type' (ej: 'http_get' o 'tcp_connect')")

            hc_type = hc_config['type']
            
            # Validar campos requeridos según el tipo
            if hc_type == 'http_get':
                if 'endpoint' not in hc_config:
                    raise ValueError(f"Servicio '{service_name}': health_check de tipo 'http_get' debe definir 'endpoint'")
            elif hc_type == 'tcp_connect':
                if 'port' not in hc_config:
                    raise ValueError(f"Servicio '{service_name}': health_check de tipo 'tcp_connect' debe definir 'port'")
            else:
                raise ValueError(f"Servicio '{service_name}': 'health_check' tiene un 'type' no válido: {hc_type}.")

            # Valores por defecto
            # Si el YML no los define se usan estos valores
            hc_config.setdefault('retries', 3)
            hc_config.setdefault('interval', 15)

def load_config(file_path: str) -> dict:
    """
    Carga y analiza un archivo de configuración YML de forma segura

    Args:
        file_path (str): La ruta completa al archivo .yml que se va a leer

    Returns:
        dict: Un diccionario de Python que representa el contenido del archivo YML
              Devuelve un diccionario vacío si el archivo YML está vacío

    Raises:
        Exception: Lanza una excepción con formato si hay un error de sintaxis
                   en el archivo YML (yaml.YAMLError)
        FileNotFoundError: Si el archivo no se encuentra (manejado por 'click'
                           en agente.py, pero se propaga si ocurre)
    """
    
    # 'with' asegura que el archivo se cierre correctamente incluso si ocurre un error
    with open(file_path, 'r', encoding='utf-8') as stream:
        try:
            config_data = yaml.safe_load(stream)
            
            # Si el archivo YML está completamente vacío, safe_load devuelve None
            # Devolvemos un diccionario vacío para que 'agente.py' pueda manejarlo consistentemente
            if config_data is None:
                return {}
            
            try:
                _validate_and_set_defaults(config_data) # Se validad la estructura y establece los defaults
            except ValueError as e:
                raise Exception(f"Error de validación de configuración: {e}")
                
            return config_data
            
        except yaml.YAMLError as e:
            # Si el YML está mal formado, PyYAML nos da detalles
            # Se captura el error y se relanza como una Excepción más clara para que 'agente.py' la muestre al usuario
            
            error_context = ""
            # 'problem_mark' nos da la ubicación del error en el archivo
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                error_context = f" (Error detectado cerca de la línea {mark.line + 1}, columna {mark.column + 1})"
            
            # Se lanza una nueva excepción con un mensaje más descriptivo
            raise Exception(f"Error de sintaxis en el archivo YML{error_context}: {e.problem}")