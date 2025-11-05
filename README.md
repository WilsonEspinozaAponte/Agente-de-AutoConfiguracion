# 🤖 Agente de Configuración Dinámica de Entornos de Pruebas
Este proyecto es un prototipo funcional de un agente de computación autonómica diseñado para automatizar el ciclo de vida de los entornos de pruebas.

El objetivo principal es eliminar la intervención manual y los errores asociados con la configuración de entornos de desarrollo y QA, permitiendo a los desarrolladores y testers obtener un entorno funcional y aislado con solo hacer un push de su código.

Esta versión inicial se enfoca en la propiedad de Autoconfiguración (Self-Configuration).

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
Asegúrate de que el servicio de Docker esté en ejecución antes de usar los comandos.

**1. Desplegar un Entorno:**
El comando deploy lee un archivo de configuración, construye las imágenes necesarias, crea una red aislada y levanta todos los servicios.

```
python agente.py deploy -f <ruta/al/archivo.yml>
```
Ejemplo de salida:
```
Iniciando despliegue desde 'example/docker-compose.yml'...
Archivo de configuración leído. 2 servicios detectados.
Construyendo imagen para 'web'...
Haciendo pull de la imagen 'redis:alpine' para 'cache'...
...
Entorno 'autotest-env-a1b2c3d4' desplegado exitosamente
Servicios creados:
  - web (ID: ...)
    Puertos: {'5000/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '5000'}]}
  - cache (ID: ...)
    Puertos: {}
```
**Importante**: Anota el nombre del entorno (ej: autotest-env-a1b2c3d4). Lo necesitarás para destruirlo.

**2. Destruir un Entorno:**
El comando teardown busca todos los recursos (contenedores, redes) etiquetados con el nombre del entorno y los elimina por completo, liberando los recursos y puertos.

```
python agente.py teardown <nombre-del-entorno>
```

Ejemplo de uso:

```
python agente.py teardown autotest-env-a1b2c3d4
```

Salida:

```
Solicitando destrucción del entorno 'autotest-env-a1b2c3d4'...
  ¿Estás seguro de que quieres eliminar... [y/N]: y
Encontrados 2 contenedores. Eliminando...
Encontradas 1 redes. Eliminando...
  Entorno 'autotest-env-a1b2c3d4' destruido exitosamente.
```

# 📝 Formato de Archivos para Pruebas
Para que el agente pueda desplegar un entorno, necesita un archivo de configuración .yml que siga un formato similar al de docker-compose.

El agente soporta actualmente las siguientes directivas:

- services: La clave raíz que contiene la definición de los servicios.
- image: El nombre de una imagen de Docker Hub para hacer pull (ej: redis:alpine, postgres:14).
- build: La ruta relativa (desde el archivo .yml) a un directorio que contiene un Dockerfile para construir una imagen local.
- ports: Un listado de mapeo de puertos HOST:CONTENEDOR.
- environment: Un listado de variables de entorno para el contenedor.

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
      - REDIS_HOST=cache # El nombre del servicio 'cache'
  # Servicio 'cache' basado en una imagen pública
  cache:
    image: "redis:alpine"
    # Nota: no necesita 'ports' si solo se accede 
    # desde el servicio 'web'
```
