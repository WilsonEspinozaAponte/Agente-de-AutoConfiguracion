# 🤖 Agente de Configuración Dinámica de Entornos de Pruebas
 **⚠️ NOTA DE VERSIÓN:  
Esta rama contiene la versión completa del sistema, diseñada para integrarse con GitHub Actions, desplegar en AWS EC2 y gestionar el tráfico mediante Traefik (Reverse Proxy).  
Incluye Balanceo de Carga real y ciclo de vida automatizado por Pull Requests.**  
  

Este proyecto implementa un Agente de Computación Autonómica capaz de gestionar entornos de prueba efímeros sin intervención humana.

# 🌟 Características Principales
## 1. GitOps & Self-Configuration:
* Al abrir un Pull Request, el agente despliega automáticamente un entorno aislado en la nube.
* Publica un comentario en el PR con una URL pública única (ej: http://autotest-123.tu-ip.nip.io).

## 2. Self-Healing (Autocorrección):
* Monitorea los contenedores en segundo plano.
* Si un servicio cae, el agente lo detecta y lo reinicia automáticamente.

## 3. Self-Optimization (Auto-optimización):
* Monitorea el uso de CPU.
* Si la carga sube (ej: >20%), escala horizontalmente creando réplicas.
* Traefik detecta las réplicas y balancea la carga automáticamente entre ellas.

## 4. Teardown Automático:
* Al cerrar o fusionar el Pull Request, el entorno se destruye para ahorrar costos.
  
# 🏗️ Arquitectura
El sistema funciona mediante la interacción de tres componentes:
1. **Orquestador (GitHub Actions)**: Detecta eventos (PR Open/Close) y envía órdenes al servidor vía SSH.
2. **Servidor Host (AWS EC2)**:
   * Ejecuta el Agente (Python).
   * Ejecuta Docker Engine (v28.x recomendado).
   * Ejecuta Traefik v3 como Proxy Inverso y Balanceador de Carga.
3. **Enrutamiento**: Se utiliza nip.io para resolución de nombres dinámica basada en la IP del servidor.

# ⚙️ Configuración de Infraestructura (Setup)
## 1. Requisitos del Servidor
  * Docker Engine: Se recomienda la versión 28.0.x para máxima compatibilidad con Traefik.
  * Puertos Abiertos (Firewall): 80 (HTTP), 8080 (Traefik Dashboard), 22 (SSH).

## 2. Configurar Traefik (El "Recepcionista")
En el servidor, crear una carpeta traefik y un archivo docker-compose.yml:  
```yaml
services:
  traefik:
    image: "traefik:v3.2"
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
      - "8080:8080"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
```
Ejecutar:
```
docker compose up -d
```
## 3. Configurar Secretos en Github
Ir a Settings > Secrets and variables > Actions en tu repositorio y añade:  
 Secreto | Descripción 
--- | --- 
 HOST_DNS | La IP Pública de tu servidor (ej: 34.197.xxx.xxx) 
 USERNAME | El usuario SSH (ej: ubuntu) 
 EC2_SSH_KEY| El contenido de la llave privada (.pem)

# 📝 Uso: El Flujo de Trabajo
Una vez configurado, no es necesario ejecutar comandos manuales.
1. Desarrolla: Haz cambios en tu código y archivo docker-compose.yml.
   * Nota: No mapees puertos (ports:) en el YAML, usa expose para que Traefik lo gestione.
2. Pull Request: Sube tu rama y abre un PR hacia main.
3. Despliegue: GitHub Actions se activará. Espera el comentario del bot.
4. Prueba: Haz clic en el enlace del comentario para ver tu entorno.
5. Limpieza: Cierra el PR y el entorno se autodestruirá.

# 🩺 Monitoreo y Debugging
Si necesitas ver qué está haciendo el agente "por detrás", conéctate por SSH al servidor.  
**Ver logs del agente en tiempo real:**
```
cd agente-app
tail -f monitor.log
```
Aquí se verán los chequeos de salud, alertas de CPU y acciones de escalado.

*Ver logs de tráfico (Traefik)**: Entra a http://TU_IP:8080 para ver el Dashboard de enrutamiento.

# 📂 Estructura del Repositorio
  * .github/workflows/: Define los pipelines de CI/CD (deploy.yml, teardown.yml).
  * agente.py: CLI principal (modificado para ejecución cloud).
  * docker_controller.py: Controlador extendido con lógica de etiquetas para Traefik y conexión de redes.
  * config_parser.py: Validador de configuración.
  * example/: Proyecto de prueba (API Flask + Redis) configurado para la nube.

## ⚠️ Notas de Compatibilidad
  * Este proyecto utiliza Traefik v3.
  * Asegúrate de que tu versión de Docker Engine sea compatible con la API del cliente de Python y Traefik (probado exitosamente en Docker v28).
