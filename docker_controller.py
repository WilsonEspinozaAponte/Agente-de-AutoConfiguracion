import docker
import os
import uuid
from docker.errors import NotFound, APIError, ImageNotFound


class EnvironmentNotFound(Exception):
    """Se lanza cuando se intenta destruir un entorno que no existe."""
    pass

# Constante para las etiquetas 
ENV_LABEL = "autotest.env.name"


def deploy_environment(config: dict, base_dir: str) -> (str, dict): # type: ignore
    """
    Despliega un entorno completo en Docker basado en la configuración.

    Crea una red aislada y luego crea e inicia cada servicio
    definido en la configuración.

    Args:
        config (dict): El diccionario de configuración parseado desde el YML
        base_dir (str): La ruta al directorio que contiene el YML, 
                        usada para resolver rutas de 'build' relativas

    Returns:
        tuple (str, dict): 
            - El nombre único del entorno generado (env_name)
            - Un diccionario con los servicios desplegados y sus detalles
    """
    try:
        # Conectarse a la API de Docker Engine
        client = docker.from_env()
        client.ping() # Verifica que la conexión es exitosa
    except Exception:
        raise ConnectionError("No se pudo conectar al Docker Engine")

    # Generar un nombre único para este entorno y sus etiquetas
    env_name = f"autotest-env-{uuid.uuid4().hex[:8]}"
    labels = {ENV_LABEL: env_name}

    deployed_services = {}

    try:
        # Crear una red aislada para el entorno
        network_name = f"{env_name}-net"
        network = client.networks.create(network_name, labels=labels)

        # Iterar y desplegar cada servicio
        for service_name, service_config in config.get('services', {}).items():
            
            container_name = f"{env_name}-{service_name}"
            
            # Determinar la imagen a usar (Build vs. Pull)
            image_name = service_config.get('image')
            if 'build' in service_config:
                # La ruta de build es relativa al archivo YML
                build_path = os.path.join(base_dir, service_config['build'])
                if not os.path.isdir(build_path):
                    raise FileNotFoundError(f"El directorio de build '{build_path}' no existe")
                
                print(f"Construyendo imagen para '{service_name}' desde {build_path}...")
                # Se etiqueta la imagen con el nombre del entorno para limpieza futura
                image_tag = f"{service_name}:{env_name}"
                image, _ = client.images.build(path=build_path, tag=image_tag, rm=True)
                image_name = image.id
            elif image_name:
                print(f"Haciendo pull de la imagen '{image_name}' para '{service_name}'...")
                try:
                    client.images.pull(image_name)
                except ImageNotFound:
                    raise Exception(f"La imagen '{image_name}' no fue encontrada")
            else:
                raise ValueError(f"El servicio '{service_name}' no define 'image' ni 'build'")

            # Preparar configuración del contenedor (puertos, env)
            port_bindings = {}
            if 'ports' in service_config:
                for port_mapping in service_config['ports']:
                    host_port, container_port = port_mapping.split(':')
                    # docker-py espera {'container_port/protocolo': host_port}
                    port_bindings[f"{container_port}/tcp"] = host_port

            environment_vars = service_config.get('environment', [])

            # Crear y arrancar el contenedor 
            print(f"Creando contenedor '{container_name}'...")
            container = client.containers.run(
                image=image_name,
                name=container_name,
                labels=labels,                     # Esencial para el teardown
                network=network.name,              # Conectar a nuestra red aislada
                ports=port_bindings,               # Mapear puertos
                environment=environment_vars,      # Establecer variables de entorno
                detach=True                        # Correr en segundo plano
            )

            # Se recarga el estado para obtener los puertos asignados
            container.reload()
            deployed_services[service_name] = {
                'id': container.id,
                'ports': container.ports
            }

        return env_name, deployed_services

    except Exception as e:
        # Limpieza en caso de fallo
        # Si algo falla a mitad del despliegue, se destruye lo que se haya creado
        print(f"Error durante el despliegue: {e}. Revirtiendo cambios...")
        destroy_environment(env_name, client) # Reutilizamos la función de destrucción
        raise # Volvemos a lanzar la excepción para que agente.py la reporte


def destroy_environment(env_name: str, client=None):
    """
    Encuentra y destruye todos los recursos (contenedores, redes) 
    asociados con un nombre de entorno

    Busca recursos usando la etiqueta 'autotest.env.name'

    Args:
        env_name (str): El nombre del entorno a destruir
        client (docker.DockerClient, optional): Un cliente de Docker existente
                                                Si es None, se crea uno nuevo
    """
    if client is None:
        try:
            client = docker.from_env()
            client.ping()
        except Exception:
            raise ConnectionError("No se pudo conectar al Docker Engine")

    # Definir el filtro para encontrar recursos por nuestra etiqueta
    label_filter = {"label": f"{ENV_LABEL}={env_name}"}

    # Encontrar y parar/eliminar todos los contenedores
    try:
        containers = client.containers.list(all=True, filters=label_filter)
        if not containers:
            # Si no hay contenedores, comprobamos redes por si algo quedó huérfano
            networks = client.networks.list(filters=label_filter)
            if not networks:
                # Si no hay ni contenedores ni redes, el entorno no existe
                raise EnvironmentNotFound()

        print(f"Encontrados {len(containers)} contenedores. Eliminando...")
        for container in containers:
            try:
                # v=True también elimina volúmenes anónimos asociados
                container.remove(force=True, v=True) 
            except NotFound:
                pass # El contenedor ya fue eliminado

    except NotFound:
        raise EnvironmentNotFound() # El filtro no encontró nada
    
    # Encontrar y eliminar todas las redes
    try:
        networks = client.networks.list(filters=label_filter)
        print(f"Encontradas {len(networks)} redes. Eliminando...")
        for network in networks:
            try:
                network.remove()
            except NotFound:
                pass # La red ya fue eliminada

    except APIError as e:
        print(f"Error de API al eliminar redes: {e}. Puede requerir limpieza manual.")