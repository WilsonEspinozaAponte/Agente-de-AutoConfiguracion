# 🤖 Agente de Configuración Dinámica de Entornos de Pruebas
Este proyecto es un prototipo funcional de un agente de computación autonómica diseñado para automatizar el ciclo de vida de los entornos de pruebas.

El objetivo principal es eliminar la intervención manual y los errores asociados con la configuración de entornos de desarrollo y QA, permitiendo a los desarrolladores y testers obtener un entorno funcional y aislado con solo hacer un push de su código.

Esta versión implementa dos propiedades autonómicas clave: **Autoconfiguración (Self-Configuration)** y **Autocorrección (Self-Healing)**.

🚀 Prerrequisitos y Configuración
Para ejecutar este agente, necesitas tener lo siguiente instalado en tu sistema:

- Python 3.9+
- Docker Engine (Docker Desktop para Windows/Mac o el servicio dockerd en Linux)

Pasos para la Instalación
Clona el repositorio:

```
git clone https://github.com/WilsonEspinozaAponte/Agente-de-AutoConfiguracion.git
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

- agente.py: El punto de entrada del programa. Define la interfaz de línea de comandos (CLI) usando click para gestionar los comandos deploy y teardown.
  
- config_parser.py: Un módulo responsable de leer y analizar de forma segura los archivos de configuración .yml (usando PyYAML).

- docker_controller.py: El corazón del agente. Contiene toda la lógica para interactuar con la API de Docker (usando docker-py) para construir imágenes, crear contenedores, gestionar redes y limpiar los recursos.

- requirements.txt: El listado de dependencias de Python necesarias para que el agente funcione.

# 🛠️ Comandos Básicos
Asegúrate de que el servicio de Docker esté en ejecución. El flujo de trabajo ahora consta de 3 comandos independientes:

**1. Desplegar un Entorno:**
El comando deploy lee un archivo de configuración, construye las imágenes necesarias, crea una red aislada y levanta todos los servicios. Al finalizar, imprime el nombre único del entorno.
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
**Importante**: Anota el nombre del entorno (ej: autotest-env-a1b2c3d4). Lo necesitarás para destruirlo.

**2. Monitorear un Entorno:**
El comando monitor inicia un bucle de monitoreo activo para un entorno que ya está desplegado. Lee las reglas health_check del archivo YML y, si un servicio falla repetidamente, lo reinicia automáticamente.

Este comando se ejecuta en su propia terminal y puede ser detenido (Ctrl+C) y reiniciado en cualquier momento sin afectar al entorno.

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


**3. Destruir un Entorno:**
El comando teardown busca todos los recursos (contenedores, redes) etiquetados con el nombre del entorno y los elimina por completo, liberando los recursos y puertos.

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

# 📝 Formato de Archivos para Pruebas
Para que el agente pueda desplegar un entorno, necesita un archivo de configuración .yml que siga un formato similar al de docker-compose.

El agente soporta actualmente las siguientes directivas:

- services: La clave raíz que contiene la definición de los servicios.
- image: El nombre de una imagen de Docker Hub para hacer pull (ej: redis:alpine, postgres:14).
- build: La ruta relativa (desde el archivo .yml) a un directorio que contiene un Dockerfile para construir una imagen local.
- ports: Un listado de mapeo de puertos HOST:CONTENEDOR.
- environment: Un listado de variables de entorno para el contenedor.
- health_check: Define las reglas para la autocorrección.
  * type: http_get o tcp_connect.
  * endpoint: (Para http_get) La ruta a chequear (ej: /health).
  * port: (Para tcp_connect) El puerto del host a chequear.
  * retries: (Opcional) Número de fallos antes de reiniciar (default: 3).
  * interval: (Opcional) Segundos entre chequeos (default: 15).

Ejemplo de docker-compose.yml Válido
```yaml
# Este archivo es leído por el agente.py

services:
  # Servicio 'web' construido desde un Dockerfile local
  web:
    build: ./api  
    ports:
      - "5000:5000" # Expone el puerto 5000 del host
    environment:
      - FLASK_ENV=development
    health_check:
      type: "http_get"
      endpoint: "/health"
      retries: 3

  # Servicio 'cache' basado en una imagen pública
  cache:
    image: "redis:alpine"
    ports:
      - "6379:6379" # Expone el puerto de Redis al host
    health_check:
      type: "tcp_connect"
      port: 6379 # El agente chequeará el puerto 6379 en localhost
```
