# 1. Usar una imagen base ligera de Python
FROM python:3.10-slim

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiar solo el archivo de requisitos primero
COPY requirements.txt .

# 4. Instalar las dependencias
RUN pip install -r requirements.txt

# 5. Copiar el código de la aplicación
COPY app.py .

# 6. Comando para ejecutar la aplicación cuando se inicie el contenedor
# Se usa --host=0.0.0.0 para que sea accesible desde fuera del contenedor
CMD ["flask", "run", "--host=0.0.0.0"]