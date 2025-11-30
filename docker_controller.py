import docker
import os
import uuid
import time
import requests
import socket
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

    # Integración de Traefik
    HOST_IP = "34.197.210.107" # IP Pública del servidor
    public_url = f"{env_name}.{HOST_IP}.nip.io" # URL 

    labels = {
        ENV_LABEL: env_name,
        "traefik.enable": "true", # Traefik gestiona este contenedor
    }

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

            # Etiquetas dinámicas
            service_labels = labels.copy()
            # Solo exponemos el servicio 'web' (o el que tenga puerto 5000/80)
            # Asumimos que el primer servicio definido con puertos es el que queremos exponer

            if service_name == "web":
                container_port = "5000" # Puerto interno estándar de Flask
                
                TRAEFIK_NETWORK = "traefik_default" 

                # Regla de Enrutamiento
                service_labels[f"traefik.http.routers.{container_name}.rule"] = f"Host(`{public_url}`)"
                # Configurar el puerto interno
                service_labels[f"traefik.http.services.{container_name}.loadbalancer.server.port"] = container_port
                
                # Le dice a Traefik: "Ignora la red interna, usa la IP de esta red para hablar conmigo"
                service_labels["traefik.docker.network"] = TRAEFIK_NETWORK
                
                print(f"Configurando Traefik para '{service_name}' en {public_url} -> :{container_port}")
            
            # Mantener soporte legacy para otros servicios si tienen puertos explícitos
            elif 'ports' in service_config:
                container_port = service_config['ports'][0].split(':')[-1]

            environment_vars = service_config.get('environment', [])

            # Crear y arrancar el contenedor 
            print(f"Creando contenedor '{container_name}'...")
            container = client.containers.run(
                image=image_name,
                name=container_name,
                labels=service_labels,                     # Se usa la nueva etiqueta de TraefiK
                network=network.name,              # Conectar a nuestra red aislada
                ports=port_bindings,               # Mapear puertos
                environment=environment_vars,      # Establecer variables de entorno
                detach=True                        # Correr en segundo plano
            )
            
            if service_name == "web":
                try:
                    # Nombre de la red donde vive Traefik 
                    TRAEFIK_NETWORK = "traefik_default" 
                    
                    # Obtenemos la referencia a la red y conectamos el contenedor
                    network_traefik = client.networks.get(TRAEFIK_NETWORK)
                    network_traefik.connect(container)
                    print(f"    Contenedor conectado a la red '{TRAEFIK_NETWORK}' para acceso externo.")
                except Exception as e:
                    print(f"    Advertencia: No se pudo conectar a la red '{TRAEFIK_NETWORK}'. Traefik podría no encontrar el servicio. Error: {e}")

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

def _perform_health_check(container: docker.models.containers.Container, 
                          service_config: dict, 
                          hc_rule: dict) -> bool:
    """
    Realiza un único sondeo de salud a un contenedor.
    Adaptado para funcionar con o sin puertos mapeados al host.
    """
    
    # 1. Obtener la IP interna del contenedor
    ip_address = None
    try:
        container.reload()
        if not container.attrs['State']['Running']:
            print(f"    - Chequeo fallido: Contenedor '{container.name}' no está 'running'.")
            return False
            
        # Intentar obtener la IP de la red del entorno primero
        # Busca redes que contengan 'autotest' o la primera que no sea bridge/traefik
        networks = container.attrs['NetworkSettings']['Networks']
        for net_name, net_data in networks.items():
            if "autotest" in net_name: 
                ip_address = net_data['IPAddress']
                break
        
        # Si no encontró la específica, usa la primera disponible que tenga IP
        if not ip_address:
            for net_data in networks.values():
                if net_data['IPAddress']:
                    ip_address = net_data['IPAddress']
                    break
        
        if not ip_address:
            raise Exception("No se pudo encontrar la IP interna del contenedor.")

    except Exception as e:
        print(f"    - Error obteniendo IP de '{container.name}': {e}")
        return False

    # 2. Realizar el chequeo
    check_type = hc_rule['type']
    
    try:
        if check_type == 'http_get':
            endpoint = hc_rule['endpoint']
            
            # LÓGICA DE PUERTO:
            # Si hay puertos mapeados, podríamos usar localhost, pero para consistencia
            # y soporte cloud sin mapeo se usa la IP INTERNA y el puerto INTERNO.
            
            # Intentar adivinar el puerto interno:
            # 1. Mirar si hay 'expose' en el YAML
            if 'expose' in service_config:
                target_port = service_config['expose'][0]
            # 2. Si no, mirar si hay 'ports' y tomar el lado derecho (contenedor)
            elif 'ports' in service_config:
                target_port = service_config['ports'][0].split(':')[-1]
            # 3. Fallback para web (asumir 5000)
            else:
                target_port = "5000"

            # Construir URL usando la IP Interna
            url = f"http://{ip_address}:{target_port}{endpoint}"
            
            # Nota: Esto funciona en Linux nativo (AWS). 
            response = requests.get(url, timeout=5)
            
            if 200 <= response.status_code < 300:
                return True
            else:
                print(f"    - HTTP fallido: {url} -> status {response.status_code}")
                return False

        elif check_type == 'tcp_connect':
            port = int(hc_rule['port'])
            # Usar la IP interna para el chequeo TCP también
            with socket.create_connection((ip_address, port), timeout=5):
                return True

    except Exception as e:
        print(f"    - Chequeo fallido para '{container.name}' ({ip_address}): {e}")
        return False
        
    return False


def monitor_environment(env_name: str, config: dict):
    """
    Inicia el bucle de monitoreo y autocorrección para un entorno.
    Esta función se ejecuta indefinidamente hasta que se interrumpe (Ctrl+C).

    Args:
        env_name (str): El nombre del entorno a monitorear.
        config (dict): El diccionario de configuración completo (para las reglas).
    """
    
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        raise ConnectionError("No se pudo conectar al Docker Engine.")

    # Se crea un mapa de estado para rastrear fallos consecutivos
    failure_counts = {}
    services_to_monitor = []

    # Se identifica qué servicios necesitan monitoreo
    for service_name, service_config in config.get('services', {}).items():
        if 'health_check' in service_config:
            failure_counts[service_name] = 0
            services_to_monitor.append(service_name)
            print(f"  Monitoreando servicio '{service_name}'...")
    
    if not services_to_monitor:
        print("  No hay servicios con 'health_check' definidos. El monitoreo no se iniciará.")
        return

    print(f"--- Iniciando bucle de monitoreo para '{env_name}' ---")
    
    initial_grace_period = 10 # 10 segundos de gracia
    print(f"  Dando un período de gracia inicial de {initial_grace_period} segundos para el arranque...")
    time.sleep(initial_grace_period)

    # Iniciar el bucle de monitoreo (se ejecuta para siempre)
    try:
        while True:
            # Pausa global entre cada ciclo de revisión
            time.sleep(10) 
            
            print(f"\n--- Ciclo de chequeo - {time.ctime()} ---")

            for service_name in services_to_monitor:
                service_config = config['services'][service_name]
                hc_rule = service_config['health_check']
                container_name = f"{env_name}-{service_name}"

                try:
                    # Obtener el contenedor (puede fallar si fue eliminado)
                    container = client.containers.get(container_name)
                    
                    # Realizar el chequeo
                    is_healthy = _perform_health_check(container, service_config, hc_rule)

                    if is_healthy:
                        # Si estaba fallando y ahora está bien, notificar
                        if failure_counts[service_name] > 0:
                            print(f"  Servicio '{service_name}' se ha recuperado.")
                        failure_counts[service_name] = 0

                        # Solo optimizamos si el contenedor está saludable
                        if 'optimization_rules' in service_config:
                            opt_rules = service_config['optimization_rules']
                            
                            # Obtener stats (stream=False devuelve una instantánea)
                            stats = container.stats(stream=False)
                            cpu_percent = _calculate_cpu_percent(stats)
                            
                            # Imprimir métrica actual 
                            print(f"     {service_name}: CPU {cpu_percent:.2f}%")

                            for rule in opt_rules:
                                if rule['metric'] == 'cpu_usage' and rule['action'] == 'scale_up':
                                    if cpu_percent > rule['threshold']:
                                        print(f"     ALERTA: CPU ({cpu_percent:.2f}%) superó umbral ({rule['threshold']}%)")
                                        # Obtener red del contenedor principal
                                        net_name = list(container.attrs['NetworkSettings']['Networks'].keys())[0]
                                        _scale_service_up(client, env_name, service_name, service_config, net_name)
                    
                    else:
                        # Incrementar fallo y notificar
                        failure_counts[service_name] += 1
                        print(f"  Servicio '{service_name}' falló chequeo. Conteo: {failure_counts[service_name]}/{hc_rule['retries']}")
                
                except NotFound:
                    print(f"  Servicio '{service_name}': Contenedor '{container_name}' no encontrado. Marcando como fallo.")
                    failure_counts[service_name] += 1
                
                except Exception as e:
                    print(f"  Error chequeando '{service_name}': {e}. Marcando como fallo.")
                    failure_counts[service_name] += 1

                # Lógica de Autocorrección (Self-Healing)
                if failure_counts[service_name] >= hc_rule['retries']:
                    print(f"  AUTOCORRECCIÓN: Servicio '{service_name}' alcanzó {failure_counts[service_name]} fallos. Reiniciando...")
                    try:
                        # Re-obtener el contenedor por si acaso
                        container_to_restart = client.containers.get(container_name)
                        container_to_restart.restart()
                        print(f"  Contenedor '{container_name}' reiniciado.")
                        # Resetear contador después de la acción
                        failure_counts[service_name] = 0
                    except NotFound:
                        print(f"  AUTOCORRECCIÓN FALLIDA: No se pudo reiniciar '{container_name}' porque no se encontró.")
                    except APIError as e:
                        print(f"  AUTOCORRECCIÓN FALLIDA: Error de API al reiniciar '{container_name}': {e}")
                        
    except KeyboardInterrupt:
        print("\n--- Bucle de monitoreo interrumpido por el usuario (Ctrl+C) ---")

def _calculate_cpu_percent(stats: dict) -> float:
    """
    Calcula el porcentaje de uso de CPU a partir de las estadísticas de Docker
    """
    try:
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        
        if system_delta > 0.0 and cpu_delta > 0.0:
            # Obtener número de núcleos
            online_cpus = stats['cpu_stats'].get('online_cpus', 1) or len(stats['cpu_stats']['cpu_usage']['percpu_usage'])
            return (cpu_delta / system_delta) * online_cpus * 100.0
    except KeyError:
        pass # La estructura de stats puede variar según versión de Docker API
    return 0.0

def _scale_service_up(client, env_name, service_name, service_config, network_name):
    """
    Despliega una nueva réplica del servicio (Escalado Horizontal).
    CORRECION: Incluye etiquetas de Traefik y conexión de red
    """
    replica_id = uuid.uuid4().hex[:6]
    container_name = f"{env_name}-{service_name}-replica-{replica_id}"
    print(f"     ESCALANDO: Creando réplica '{container_name}'...")

    try:
        # Resolver Imagen
        image_name = service_config.get('image')
        if 'build' in service_config:
            image_name = f"{service_name}:{env_name}"
        
        # Configuración
        environment_vars = service_config.get('environment', [])
        
        # 1. Definimos las etiquetas base
        labels = {ENV_LABEL: env_name, "autotest.type": "replica"}
        
        # 2. Si es el servicio web, agregamos etiquetas de Traefik
        # Usamos el mismo nombre de Router y Servicio que el original para que Traefik los agrupe.
        if service_name == "web":
            HOST_IP = "34.197.210.107"
            public_url = f"{env_name}.{HOST_IP}.nip.io"
            TRAEFIK_NETWORK = "traefik_default"
            
            labels["traefik.enable"] = "true"
            labels["traefik.docker.network"] = TRAEFIK_NETWORK
            # Usamos el nombre del contenedor original como identificador del servicio
            # para que Traefik sepa que esta réplica pertenece al mismo grupo.
            original_container_name = f"{env_name}-{service_name}"
            
            labels[f"traefik.http.routers.{original_container_name}.rule"] = f"Host(`{public_url}`)"
            labels[f"traefik.http.services.{original_container_name}.loadbalancer.server.port"] = "5000"

        # Crear contenedor
        container = client.containers.run(
            image=image_name,
            name=container_name,
            labels=labels,
            network=network_name,
            environment=environment_vars,
            detach=True
        )
        
        # 3. Conectar a la red de Traefik (Igual que en deploy)
        if service_name == "web":
            try:
                TRAEFIK_NETWORK = "traefik_default" 
                network_traefik = client.networks.get(TRAEFIK_NETWORK)
                network_traefik.connect(container)
                print(f"     Réplica conectada a '{TRAEFIK_NETWORK}'.")
            except Exception as e:
                print(f"     Error conectando réplica a red pública: {e}")

        print(f"     Réplica '{container_name}' iniciada exitosamente.")
        
    except Exception as e:
        print(f"     Error al escalar servicio '{service_name}': {e}")