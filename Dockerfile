# Usar una imagen base de Python ligera
FROM python:3.11-slim

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar algunas librerías si fuera necesario
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar el archivo de requerimientos
COPY requirements.txt .

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el contenido del proyecto al contenedor
COPY . .

# Crear la carpeta de runtime para la base de datos si no existe
RUN mkdir -p runtime

# Configurar el PYTHONPATH para que encuentre el módulo 'engine'
ENV PYTHONPATH=/app

# Exponer el puerto que usa FastAPI
EXPOSE 8000

# Comando para ejecutar la aplicación
# Usamos uvicorn directamente para mejor soporte de señales en Docker
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
