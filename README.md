# 🤖 Agente de Configuración Dinámica de Entornos de Pruebas
 **⚠️ NOTA DE VERSIÓN: Esta rama contiene el prototipo diseñado para ejecución local. Funciona sobre un Docker Engine en una sola máquina y está destinado a validar la lógica de los agentes autonómicos. Para la versión con despliegue en la nube, balanceo de carga y CI/CD integrado, por favor consulte la rama del MVP final.**  
  

Este proyecto es un prototipo funcional de un agente de computación autonómica diseñado para automatizar el ciclo de vida de los entornos de pruebas.

El objetivo principal es eliminar la intervención manual y los errores asociados con la configuración de entornos de desarrollo y QA, permitiendo a los desarrolladores y testers obtener un entorno funcional y aislado con solo hacer un push de su código.

Esta versión implementa tres propiedades autonómicas clave:
 1. **Autoconfiguración (Self-Configuration)**: Despliegue automático de recursos.
 2. **Autocorrección (Self-Healing)**: Detección de fallos y reinicio de servicios.
 3. **Auto-optimización (Self-Optimization)**: Escalado horizontal reactivo basado en uso de CPU.

# 🚀 Prerrequisitos y Configuración
Para ejecutar este agente, necesitas tener lo siguiente instalado en tu sistema:

- Python 3.9+
- Docker Engine (Docker Desktop para Windows/Mac o el servicio dockerd en Linux)

Pasos para la Instalación
Clona el repositorio:

```
git clone https://github.com/Esap28/Agente-de-AutoConfiguracion.git
cd Agente-de-AutoConfiguracion
```
Crea y activa un entorno virtual:

```
# En Windows
python -m venv venv
.\venv\Scripts\activate

# En macOS/Linux
python3 -m venv venv
source venv/bin/activate
```
Instala las dependencias:
```
pip install -r requirements.txt
```

# 📂 Archivos del Proyecto
Este repositorio contiene el núcleo del agente autonómico:

- agente.py: El punto de entrada del programa. Define la interfaz de línea de comandos (CLI) usando click.
  
- config_parser.py: Responsable de leer, analizar y validar los archivos de configuración .yml.

- docker_controller.py: Contiene toda la lógica para interactuar con la API de Docker, monitorear salud, calcular métricas de CPU y ejecutar acciones de escalado.

- requirements.txt: Dependencias del proyecto

# 🛠️ Comandos Básicos
Asegúrate de que el servicio de Docker esté en ejecución.

**1. Desplegar un Entorno:**  
Lee el archivo de configuración, construye imágenes, crea una red aislada y levanta los servicios.
```
python agente.py deploy -f <ruta/al/archivo.yml>
```
Ejemplo de salida:
```
Iniciando despliegue desde 'example/docker-compose.yml'...
Archivo de configuración leído. 2 servicios detectados...
   ¡Entorno 'autotest-env-a1b2c3d4' desplegado exitosamente!
Servicios creados:
  - web (ID: ...)
    Puertos: {'5000/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '5000'}]}
  - cache (ID: ...)
    Puertos: {'6379/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '6379'}]}
```
**Importante**: Anota el nombre del entorno (ej: autotest-env-a1b2c3d4) para su posterior monitoreo o eliminación.. 

**2. Monitorear un Entorno (Healing & Optimization):**  
Inicia un bucle activo que:
1. Verifica la salud de los servicios (Health Checks).
2. Calcula el uso de CPU de los contenedores.
3. Reinicia contenedores si fallan repetidamente (Self-Healing).
4. Crea réplicas si la CPU supera el umbral definido (Self-Optimization).

```
python agente.py monitor -f <ruta/al/archivo.yml> <nombre-del-entorno>
```

Ejemplo de salida (al detectar una falla):
```
(venv) PS> python agente.py monitor -f ejemplo/docker-compose.yml autotest-env-a1b2c3d4

Reglas de monitoreo cargadas desde '...docker-compose.yml'.
Iniciando modo de monitoreo para 'autotest-env-a1b2c3d4'...
(Presiona Ctrl+C para detener el agente y el monitoreo)...
--- [Ciclo de chequeo - ...] ---
    - Chequeo HTTP fallido para '...-web': No se pudo conectar...
      Servicio 'web' falló chequeo. Conteo: 1/3
...
--- [Ciclo de chequeo - ...] ---
    - Chequeo HTTP fallido para '...-web': No se pudo conectar...
      Servicio 'web' falló chequeo. Conteo: 3/3
      AUTOCORRECCIÓN: Servicio 'web' alcanzó 3 fallos. Reiniciando...
      Contenedor 'autotest-env-a1b2c3d4-web' reiniciado.
```

Ejemplo de salida (Escalado por CPU):
```
(venv) PS> python agente.py monitor -f ejemplo/docker-compose.yml autotest-env-a1b2c3d4

...
--- [Ciclo de chequeo - ...] ---
      web: CPU 90.0%
       ALERTA: CPU (90.00%) superó umbral (80%)
       ESCALANDO: Creando réplica 'autotest-env-a1b2c3d4-web-replica-07ffa7'...
       Réplica 'autotest-env-a1b2c3d4-web-replica-07ffa7' iniciada exitosamente.
```

**3. Destruir un Entorno:**
Elimina todos los recursos (contenedores, réplicas y redes) asociados al entorno.
```
python agente.py teardown <nombre-del-entorno>
```

Ejemplo de uso:

```
(venv) PS> python agente.py teardown autotest-env-a1b2c3d4
```

Salida:

```
Solicitando destrucción del entorno 'autotest-env-a1b2c3d4'...
  ¿Estás seguro de que quieres eliminar... [y/N]: y
Encontrados 2 contenedores. Eliminando...
Encontradas 1 redes. Eliminando...
  Entorno 'autotest-env-a1b2c3d4' destruido exitosamente
```

# 📝 Formato de Archivos(.yml)
El agente requiere un archivo YAML extendido. Soporta las directivas estándar de Docker Compose más las secciones autonómicas.

Directivas Soportadas:
- **Estándar**: services, image, build, ports, environment.
- health_check (Autocorrección):
  * type: http_get o tcp_connect.
  * endpoint / port: Objetivo del chequeo.
  * retries: Intentos antes de reiniciar.
- optimization_rules (Auto-optimización):
  * metric: Métrica a evaluar (actualmente soporta cpu_usage).
  * threshold: Porcentaje límite (ej: 70).
  * action: Acción a tomar (ej: scale_up).
  * replicas: Cantidad de contenedores a agregar.

Ejemplo de docker-compose.yml Válido
```yaml
# Este archivo es leído por el agente.py

services:
  web:
    build: ./api  
    ports:
      - "5000:5000"
    # Reglas de Autocorreción
    health_check:
      type: "http_get"
      endpoint: "/health"
      retries: 3

    # Reglas de Auto-optimización
    optimization_rules:
      - metric: "cpu_usage"
        threshold: 70       # Si CPU > 70%
        action: "scale_up"  # Escalar horizontalmente
        replicas: 1
```

# ⚠️ Limitaciones de la Versión Local  
Al ser un prototipo diseñado para ejecutarse en una sola máquina host sin un orquestador complejo (como Kubernetes) ni un Proxy Inverso configurado, existen las siguientes limitaciones:
1. **Sin Balanceo de Carga:** Cuando el agente escala y crea réplicas (ej: web-replica-1), estas se conectan a la red interna pero no reciben tráfico externo automáticamente. El puerto 5000 del host sigue apuntando solo al contenedor original.
2. **Puertos de Réplicas:** Las réplicas creadas por Self-Optimization no exponen puertos al host para evitar errores de tipo Address already in use.
3. **Alcance de Red:** Los Health Checks dependen de la visibilidad de localhost.

Estas limitaciones se resuelven en la versión Cloud MVP mediante el uso de un Proxy Inverso (Traefik) y descubrimiento de servicios dinámico.
