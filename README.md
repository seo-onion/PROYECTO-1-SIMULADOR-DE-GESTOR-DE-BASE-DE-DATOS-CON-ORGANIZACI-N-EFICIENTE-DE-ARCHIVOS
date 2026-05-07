# PROYECTO 1: Simulador de Gestor de BD (BD2)

## Estado actual
El proyecto ya no está solo en la etapa de scanner. Actualmente incluye:

- `parser/`: scanner y parser del subconjunto SQL del proyecto.
- `DB_source/`: manejo del archivo principal de la tabla en binario.
- `Data_structures/B+TREE/`: índices persistentes `Sequential`, `Extendible Hash`, `B+Tree` y `RTree`.
- `engine/`: clase `Engine` que conecta parser, heap file e índices.
- `backend/`: API HTTP en FastAPI para futuras conexiones con frontend.

## Qué hace `Engine`
La clase `Engine` centraliza la ejecución de consultas SQL y la coordinación de estructuras. Soporta:

- `CREATE TABLE ...`
- `CREATE TABLE ... FROM FILE ...`
- `INSERT INTO ... VALUES (...)`
- `SELECT * FROM ... WHERE <col> = <valor>`
- `SELECT * FROM ... WHERE <col> BETWEEN <v1> AND <v2>`
- `SELECT * FROM ... WHERE <col> IN (POINT(...), RADIUS <r>)`
- `SELECT * FROM ... WHERE <col> IN (POINT(...), K <k>)`
- `DELETE FROM ... WHERE <col> = <valor>`

Además:

- crea y persiste el catálogo de tablas en `runtime/catalog.json`
- crea los archivos binarios de cada tabla
- mantiene sincronizados los índices al insertar y borrar
- usa el índice correcto cuando la consulta lo permite

## Tipos e índices soportados
Tipos de columna soportados por el motor:

- `INT`, `INTEGER`, `SERIAL`
- `FLOAT`, `REAL`, `DOUBLE`
- `VARCHAR(n)`, `CHAR(n)`, `STRING(n)`, `TEXT`
- `POINT2D`, `POINT3D` o `POINT(n)` para columnas espaciales

Técnicas de índice soportadas:

- `SEQUENTIAL`
- `HASH`
- `BTREE` o `B+TREE`
- `RTREE`

Ejemplo:

```sql
CREATE TABLE lugares (
  id INT INDEX HASH,
  nombre VARCHAR(50),
  score FLOAT INDEX BTREE,
  ubicacion POINT2D INDEX RTREE
);
```

## Librerías necesarias
El backend y el motor requieren Python 3.11+ y estas librerías:

```bash
pip install fastapi uvicorn pydantic
```

No se necesita un motor de base de datos externo.

## Cómo ejecutar el backend
Desde la raíz del proyecto:

```bash
python -m backend.app
```

El backend levanta en:

```text
http://127.0.0.1:8000
```

Endpoints disponibles:

- `GET /health`
- `GET /tables`
- `GET /tables/{table_name}`
- `POST /query`

Ejemplo de request:

```json
POST /query
{
  "sql": "SELECT * FROM demo WHERE id = 1;"
}
```

## Cómo usar el scanner por lote
Si solo quieres procesar archivos `.txt` del directorio `input/`:

```bash
python -m parser.main
```

Esto genera archivos `*_tokens.txt` en la misma carpeta.

## Flujo recomendado de prueba
1. Levantar el backend con `python -m backend.app`.
2. Crear una tabla con `POST /query`.
3. Insertar registros.
4. Ejecutar consultas exactas, por rango o espaciales.
5. Verificar el catálogo con `GET /tables`.

## Pendiente
Todavía faltan piezas del enunciado original:

- métricas reales de accesos a página
- simulación de concurrencia
- frontend de visualización
- visualización gráfica de resultados espaciales
