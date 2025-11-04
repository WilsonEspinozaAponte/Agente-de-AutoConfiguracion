import click
import sys
import os

try:
    import config_parser
    import docker_controller
except ImportError:
    print("Error: No se encontraron los módulos 'config_parser.py' o 'docker_controller.py'.") # Deben estar en el mismo directorio
    sys.exit(1)

# Definición del Grupo de Comandos Principal

@click.group()
def cli():
    """
    Agente Autonómico para la Configuración Dinámica de Entornos de Pruebas.
    
    Este CLI permite desplegar y destruir entornos basados en archivos 
    de configuración YML.
    """
    pass

# Comando 'deploy'

@cli.command()
@click.option(
    '--file', '-f',
    type=click.Path(exists=True, readable=True, dir_okay=False, resolve_path=True),
    required=True,
    help='Ruta al archivo docker-compose.yml o manifiesto personalizado.'
)
def deploy(file):
    """
    Despliega un nuevo entorno de pruebas basado en un archivo de configuración.
    """
    click.echo(f" Iniciando despliegue desde '{click.format_filename(file)}'...")

    # Leer y analizar el archivo de configuración
    try:
        config_data = config_parser.load_config(file)
        if not config_data or 'services' not in config_data:
            click.secho(" ERROR: El archivo de configuración está vacío o no tiene la sección 'services'.", fg="red")
            sys.exit(1)
            
        click.secho(f" Archivo de configuración leído. {len(config_data['services'])} servicios detectados.", fg="green")

    except Exception as e:
        click.secho(f" ERROR al analizar el archivo YML: {e}", fg="red")
        sys.exit(1)

    # Llamar al controlador de Docker para el despliegue
    try:
        # Se pasa la configuración y el directorio base 
        base_dir = os.path.dirname(file)
        env_name, deployed_services = docker_controller.deploy_environment(config_data, base_dir)
        
        click.secho(f"\n Entorno '{env_name}' desplegado exitosamente", fg="green", bold=True)
        click.echo(" Servicios creados:")
        for service_name, service_info in deployed_services.items():
            click.echo(f"  - {service_name} (ID: {service_info['id'][:12]})")
            if service_info['ports']:
                 click.echo(f"    Puertos: {service_info['ports']}")

    except Exception as e:
        click.secho(f"\n ERROR durante el despliegue en Docker: {e}", fg="red", bold=True)
        sys.exit(1)

# Comando 'teardown'

@cli.command()
@click.argument('env_name')
def teardown(env_name):
    """
    Destruye un entorno de pruebas completo por su nombre.
    
    ENV_NAME es el nombre único del entorno.
    """
    click.echo(f" Solicitando destrucción del entorno '{env_name}'...")

    # Pedir confirmación para evitar borrados accidentales
    if not click.confirm(f" ¿Estás seguro de que quieres eliminar permanentemente el entorno '{env_name}' y todos sus volúmenes?"):
        click.echo("Operación cancelada.")
        return

    #  Llamar al Controlador de Docker para la Destrucción
    try:
        docker_controller.destroy_environment(env_name)
        click.secho(f" Entorno '{env_name}' destruido exitosamente.", fg="green", bold=True)
        
    except docker_controller.EnvironmentNotFound:
        click.secho(f" Advertencia: No se encontró ningún entorno con el nombre '{env_name}'.", fg="yellow")
        
    except Exception as e:
        click.secho(f"\n ERROR durante la destrucción: {e}", fg="red", bold=True)
        sys.exit(1)

# Punto de Entrada Principal 

if __name__ == "__main__":
    cli()