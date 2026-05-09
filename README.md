# PROYECTO 1: Simulador de Gestor de BD (BD2)

## Estado actual
El proyecto ya no está solo en la etapa de scanner. Actualmente incluye:

- `parser/`: scanner y parser del subconjunto SQL del proyecto.
- `DB_source/`: manejo del archivo principal de la tabla en binario.
- `Data_structures/B+TREE/`: índices persistentes `Sequential`, `Extendible Hash`, `B+Tree` y `RTree`.
- `engine/`: clase `Engine` que conecta parser, heap file e índices.
- `backend/`: API HTTP en FastAPI para futuras conexiones con frontend.

## Analizador Sintáctico (SQL Parser)

> El módulo del Parser es el componente encargado de recibir las consultas en texto plano desde el Frontend, realizar el análisis léxico y sintáctico, y generar un Árbol de Sintaxis Abstracta (AST) tipado. Este AST es el que el Motor de Base de Datos procesa para ejecutar operaciones sobre las estructuras de indexación (B+ Tree, R-Tree, etc.)

### Arquitectura y Componentes

> La implementación sigue un modelo de **Análisis Sintáctico Descendente Recursivo** (Recursive Descent Parsing):

* **Scanner (`scanner.py`):** Realiza el análisis léxico convirtiendo la cadena de entrada en un flujo de tokens (`TokenType`). Maneja correctamente espacios en blanco, comentarios y reconoce números negativos/decimales para coordenadas espaciales.
* **AST Tipado (`sql_parser.py`):** Utiliza `dataclasses` de Python (como `SelectCommand`, `CreateTableCommand`) para representar las sentencias. Esto proporciona una estructura inmutable, con tipado fuerte y autocompletado, facilitando la integración con el motor de base de datos.
* **Parser (`sql_parser.py`):** La clase `SQLParser` consume los tokens y valida la gramática formal definida para el proyecto.

### Gramática Formal (EBNF)

El parser está construido sobre la siguiente gramática formal, diseñada para soportar estrictamente el subconjunto de SQL requerido por el proyecto:

#### Estructura General

```ebnf
<program>      ::= { <statement> }
<statement>    ::= ( <create_stmt> | <select_stmt> | <insert_stmt> | <delete_stmt> ) ";"
```

#### Sentencia CREATE TABLE
```ebnf
<create_stmt>  ::= "CREATE" "TABLE" <id> "(" <column_list> ")" [ "FROM" "FILE" <string> ]
<column_list>  ::= <column_def> { "," <column_def> }
<column_def>   ::= <id> <type_def> [ "INDEX" <index_tech> ]

<type_def>     ::= <id> { <id> | <num> | "(" | ")" }

<index_tech>   ::= "Sequential" | "Extendible" | "BPlus" | "RTree" | <id>
```

#### Sentencia SELECT y Consultas espaciales
```ebnf
<select_stmt>  ::= "SELECT" "*" "FROM" <id> [ "WHERE" <condition> ]

<condition>    ::= <point_condition> 
                 | <range_condition> 
                 | <spatial_condition>

<point_condition>   ::= <id> <operator> <value>

<range_condition>   ::= <id> "BETWEEN" <value> "AND" <value>

<spatial_condition> ::= <id> "IN" "(" "POINT" "(" <num> "," <num> ")" "," <spatial_param> ")"

<spatial_param>     ::= "RADIUS" <num> 
                      | "K" <num>

<operator>          ::= "=" | "<" | ">" | "<=" | ">="
```

#### Sentencia INSERT
```ebnf
<insert_stmt>  ::= "INSERT" "INTO" <id> "VALUES" "(" <value_list> ")"
<value_list>   ::= <value> { "," <value> }
```

#### Sentencia DELETE
```ebnf
<delete_stmt>  ::= "DELETE" "FROM" <id> "WHERE" <id> "=" <value>
```

#### Terminales Generales
```ebnf
<id>           ::= ID         /* Cualquier identificador: nombres de tablas, columnas, etc. */
<num>          ::= NUM        /* Números enteros o decimales (incluyendo negativos) */
<string>       ::= STRING     /* Cadenas de texto entre comillas */
<value>        ::= <num> | <string>
```


### Subconjunto SQL Soportado

> El parser traduce las siguientes sentencias a objetos `Command` específicos:

#### 1. CREATE TABLE
* Define tablas con múltiples columnas y tipos de datos variables.
* Soporta tipos complejos como `VARCHAR(50) NOT NULL` mediante un sistema de seguimiento de profundidad de paréntesis.
* Permite especificar la técnica de indexación: `INDEX <técnica>` (ej. BPlus, RTree, Sequential, Extendible).
* Soporta carga masiva de datos: `FROM FILE <path>`.

#### 2. SELECT
* **Búsquedas Simples:** Soporta operadores de comparación `=`, `<`, `>`, `<=`, `>=` en la cláusula `WHERE`.
* **Búsquedas por Rango:** Implementa la sintaxis `BETWEEN <v1> AND <v2>`.
* **Consultas Espaciales (R-Tree):**
    * Búsqueda por radio: `IN (POINT (<x>, <y>), RADIUS <r>)`.
    * Búsqueda de K vecinos: `IN (POINT (<x>, <y>), K <k>)`.

#### 3. INSERT INTO
* Inserta nuevos registros especificando la tabla y la lista de valores: `INSERT INTO <tabla> VALUES (...);`.

#### 4. DELETE FROM
* Elimina registros basados en una condición de igualdad: `DELETE FROM <tabla> WHERE <col> = <valor>;`.

### Funciones y Lógica Principal

* `parse()`: Punto de entrada que procesa el flujo de tokens hasta encontrar el fin de archivo (`EOF`), devolviendo una lista de comandos ejecutables.
* `_parse_condition()`: Método central para la resolución de la cláusula `WHERE`. Identifica si se trata de una condición simple (`SimpleCondition`), de rango (`BetweenCondition`) o espacial (`RadiusCondition`/`KNNCondition`).
* `_parse_type_name()`: Algoritmo que permite capturar definiciones de tipos de datos extensas (con espacios y paréntesis internos) de forma segura.
* **Manejo de Errores:** Lanza la excepción personalizada `SQLParserError` ante fallos sintácticos, detallando la línea y columna exacta del error para facilitar la depuración.

### Ejemplo de Salida (AST)

Para una consulta espacial como:
`SELECT * FROM locales WHERE posicion IN (POINT (10.5, 20.0), RADIUS 5.0);`

El parser genera el siguiente objeto:
```python
SelectCommand(
    table_name='locales',
    condition=RadiusCondition(
        column='posicion',
        point=(10.5, 20.0),
        radius=5.0
    )
)
```

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

## Endpoints disponibles

- `GET /health`
- `GET /tables`
- `GET /tables/{table_name}`
- `POST /query`

## Ejemplos JSON por endpoint

### `GET /health`
Response:

```json
{
  "ok": true,
  "service": "db-engine-backend"
}
```

### `GET /tables`
Response:

```json
{
  "ok": true,
  "tables": [
    {
      "name": "alumnos",
      "db_file": "C:/ruta/al/proyecto/runtime/tables/alumnos/alumnos.bin",
      "struct_format": "i 50s f",
      "source_path": null,
      "columns": [
        {
          "name": "id",
          "type_name": "INT",
          "index_technique": "HASH",
          "struct_tokens": ["i"],
          "dimension": 1,
          "length": null
        },
        {
          "name": "nombre",
          "type_name": "VARCHAR(50)",
          "index_technique": null,
          "struct_tokens": ["50s"],
          "dimension": 1,
          "length": 50
        },
        {
          "name": "promedio",
          "type_name": "FLOAT",
          "index_technique": "BTREE",
          "struct_tokens": ["f"],
          "dimension": 1,
          "length": null
        }
      ],
      "indexes": ["id", "promedio"],
      "row_count": 2
    }
  ]
}
```

### `GET /tables/{table_name}`
Ejemplo:

```text
GET /tables/alumnos
```

Response:

```json
{
  "ok": true,
  "table": {
    "name": "alumnos",
    "db_file": "C:/ruta/al/proyecto/runtime/tables/alumnos/alumnos.bin",
    "struct_format": "i 50s f",
    "source_path": null,
    "columns": [
      {
        "name": "id",
        "type_name": "INT",
        "index_technique": "HASH",
        "struct_tokens": ["i"],
        "dimension": 1,
        "length": null
      },
      {
        "name": "nombre",
        "type_name": "VARCHAR(50)",
        "index_technique": null,
        "struct_tokens": ["50s"],
        "dimension": 1,
        "length": 50
      },
      {
        "name": "promedio",
        "type_name": "FLOAT",
        "index_technique": "BTREE",
        "struct_tokens": ["f"],
        "dimension": 1,
        "length": null
      }
    ],
    "indexes": ["id", "promedio"],
    "row_count": 2
  }
}
```

### `POST /query`
Request:

```json
{
  "sql": "CREATE TABLE alumnos (id INT INDEX HASH, nombre VARCHAR(50), promedio FLOAT INDEX BTREE);"
}
```

Response:

```json
{
  "ok": true,
  "results": [
    {
      "operation": "create_table",
      "table": "alumnos",
      "columns": [
        {
          "name": "id",
          "type_name": "INT",
          "index_technique": "HASH",
          "struct_tokens": ["i"],
          "dimension": 1,
          "length": null
        },
        {
          "name": "nombre",
          "type_name": "VARCHAR(50)",
          "index_technique": null,
          "struct_tokens": ["50s"],
          "dimension": 1,
          "length": 50
        },
        {
          "name": "promedio",
          "type_name": "FLOAT",
          "index_technique": "BTREE",
          "struct_tokens": ["f"],
          "dimension": 1,
          "length": null
        }
      ],
      "imported_rows": 0
    }
  ],
  "stats": {
    "execution_ms": 8.4,
    "disk_reads": null,
    "disk_writes": null
  }
}
```

### `POST /query` para insertar
Request:

```json
{
  "sql": "INSERT INTO alumnos VALUES (1, 'Ana', 17.5);"
}
```

Response:

```json
{
  "ok": true,
  "results": [
    {
      "operation": "insert",
      "table": "alumnos",
      "db_offset": 28,
      "row": {
        "id": 1,
        "nombre": "Ana",
        "promedio": 17.5
      }
    }
  ],
  "stats": {
    "execution_ms": 3.1,
    "disk_reads": null,
    "disk_writes": null
  }
}
```

### `POST /query` para seleccionar
Request:

```json
{
  "sql": "SELECT * FROM alumnos WHERE id = 1;"
}
```

Response:

```json
{
  "ok": true,
  "results": [
    {
      "operation": "select",
      "table": "alumnos",
      "count": 1,
      "rows": [
        {
          "id": 1,
          "nombre": "Ana",
          "promedio": 17.5,
          "_db_offset": 28
        }
      ]
    }
  ],
  "stats": {
    "execution_ms": 1.8,
    "disk_reads": null,
    "disk_writes": null
  }
}
```

### `POST /query` para borrar
Request:

```json
{
  "sql": "DELETE FROM alumnos WHERE id = 1;"
}
```

Response:

```json
{
  "ok": true,
  "results": [
    {
      "operation": "delete",
      "table": "alumnos",
      "deleted_count": 1,
      "rows": [
        {
          "id": 1,
          "nombre": "Ana",
          "promedio": 17.5,
          "_db_offset": 28
        }
      ]
    }
  ],
  "stats": {
    "execution_ms": 2.0,
    "disk_reads": null,
    "disk_writes": null
  }
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

## Flujo de almacenamiento y paginacion

### `PageManager`

`PageManager` es la capa de E/S paginada del proyecto. Evita que el resto del codigo lea o escriba archivos binarios directamente.

Responsabilidades:

- leer paginas completas de 4096 bytes;
- escribir paginas completas de 4096 bytes;
- permitir lecturas/escrituras por offset con `read_at()` y `write_at()`;
- preservar el resto de una pagina cuando solo se modifica una parte;
- contar paginas leidas y escritas en `disk_reads` y `disk_writes`.

Ejemplo:

```text
write_at(offset=20, data=32 bytes)
```

Internamente:

```text
1. calcula que pagina contiene el offset 20;
2. lee esa pagina si debe preservar bytes existentes;
3. reemplaza los 32 bytes dentro de la pagina;
4. escribe la pagina completa;
5. incrementa el contador de escrituras.
```

`PagedFile` es un adaptador pequeno con metodos tipo archivo (`seek`, `read`, `write`, `truncate`). Se usa para que los indices puedan seguir trabajando con una interfaz parecida a `open()`, pero pasando por `PageManager`.

### `Table_file_managment`

`Table_file_managment.py` maneja el archivo fisico principal de cada tabla, tambien llamado heap file.

Este archivo guarda:

```text
header + registros fisicos
```

El header contiene:

- tamano del header;
- numero de registros;
- tamano de cada registro;
- formato fisico `struct`;
- numero de atributos fisicos;
- flags de indices.

Los registros se guardan al final del archivo. Cada registro termina con un byte `tombstone` para marcar borrado logico.

### Flujo general de la BD

`CREATE TABLE`:

```text
SQL -> parser -> engine -> init_main_db()
```

`init_main_db()` crea el archivo vacio, construye el header inicial y lo escribe con `__write_header()`, que usa `PageManager`. El engine guarda el schema logico en `runtime/catalog.json`.

`INSERT`:

```text
SQL -> parser -> engine -> insert_record() -> indices
```

`insert_record()` lee el header, calcula el offset fisico del nuevo registro, escribe el registro, actualiza `reg_number` y devuelve el `db_offset`. Luego el engine inserta en cada indice:

```text
clave -> db_offset
```

`SELECT`:

```text
SQL -> parser -> engine -> indice -> heap file
```

El indice devuelve offsets fisicos. Luego el engine lee las filas completas desde el heap file usando `iter_records()` o lectura por offset.

`DELETE`:

```text
SQL -> parser -> engine -> indice -> delete_record()
```

`delete_record()` marca el tombstone del registro en el heap file. Despues el engine elimina la entrada correspondiente de cada indice.

### Como ayuda esto a la paginacion

Antes, varias funciones hacian:

```python
open(...).read()
open(...).write()
```

Ahora el flujo principal pasa por:

```python
PageManager.read_at()
PageManager.write_at()
```

Eso permite defender que:

- la E/S se hace a nivel de paginas fijas;
- cada operacion puede reportar paginas leidas y escritas;
- el heap file no se carga completo en memoria;
- los indices guardan punteros al heap file en vez de duplicar filas completas.

## Pendiente
Todavía faltan piezas del enunciado original:

- métricas reales de accesos a página
- simulación de concurrencia
- frontend de visualización
- visualización gráfica de resultados espaciales
