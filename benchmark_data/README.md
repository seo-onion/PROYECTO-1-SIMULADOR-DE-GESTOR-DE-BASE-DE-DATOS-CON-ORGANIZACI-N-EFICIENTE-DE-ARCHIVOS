# Datos y pruebas de eficiencia

Esta carpeta contiene scripts para generar datasets aleatorios de 1 000, 10 000 y 100 000 registros, y un runner para probar la BD con consultas simples sobre todos los indices.

## Generar datasets

Desde la raiz del proyecto:

```bash
python benchmark_data/generate_1000.py
python benchmark_data/generate_10000.py
python benchmark_data/generate_100000.py
```

Los CSV se escriben en:

```text
benchmark_data/generated/random_1000.csv
benchmark_data/generated/random_10000.csv
benchmark_data/generated/random_100000.csv
```

## Ejecutar pruebas

Para un solo tamano:

```bash
python benchmark_data/run_tests.py --size 1000 --index hash
```

Indices disponibles:

```text
hash
sequential
btree
rtree
all
```

Para todos los tamanos usando un indice:

```bash
python benchmark_data/run_tests.py --all --index hash
```

Para correr todos los indices de un tamano:

```bash
python benchmark_data/run_tests.py --size 1000 --index all
```

El runner:

- genera el CSV si no existe;
- crea una tabla nueva en un runtime separado para el indice elegido;
- carga datos con `CREATE TABLE ... FROM FILE`;
- ejecuta consultas sobre Hash, Sequential, B+Tree y R-Tree;
- guarda resultados en `benchmark_data/results/`.

Nota: `--index all` puede tardar bastante porque carga el CSV una vez por tecnica de indice. Para experimentos de 100 000 registros conviene ejecutar una tecnica a la vez.

## Tabla generada

Cada fila tiene:

| columna | tipo | indice |
|---|---|---|
| `id` | `INT` | `HASH` |
| `seq_key` | `INT` | `SEQUENTIAL` |
| `score` | `FLOAT` | `BTREE` |
| `pos` | `POINT2D` | `RTREE` |
| `name` | `VARCHAR(24)` | sin indice |

## Cargar datasets externos para el front

El script `load_external_datasets.py` prepara los CSV en el formato que espera el engine y ejecuta `CREATE TABLE ... FROM FILE` sin modificar la implementacion de la BD.

Preparar CSVs sin cargar tablas:

```bash
python benchmark_data/load_external_datasets.py --dataset all --csv-only
```

Cargar en el runtime local que usa el backend:

```bash
python benchmark_data/load_external_datasets.py --dataset pokemon --mode local
python benchmark_data/load_external_datasets.py --dataset customers_10000 --mode local
python benchmark_data/load_external_datasets.py --dataset customers_100000 --mode local
python benchmark_data/load_external_datasets.py --dataset airbnb --mode local
```

Si el backend ya esta prendido y quieres que el front vea la tabla en esa misma sesion, manda la carga por el endpoint:

```bash
python benchmark_data/load_external_datasets.py --dataset pokemon --mode backend --api-url http://127.0.0.1:8000/query
```

Para repetir desde cero en modo local, usa un runtime limpio:

```bash
python benchmark_data/load_external_datasets.py --dataset all --mode local --reset-runtime
```

Datasets soportados:

- `pokemon`: usa `pokemon_complete_2025.csv` y crea `pokemon_complete_2025` con `pokedex_id INDEX HASH`, `name INDEX SEQUENTIAL` y `base_stat_total INDEX BTREE`.
- `customers_10000`: usa `customers-10000.csv`, normaliza headers y crea `customers_10000` con `id INDEX HASH`, `Customer_Id INDEX SEQUENTIAL` y `Subscription_Date INDEX BTREE`.
- `customers_100000`: usa `customers-100000.csv`, normaliza headers y crea `customers_100000` con `id INDEX HASH`, `Customer_Id INDEX SEQUENTIAL`, `First_Name INDEX HASH` y `Subscription_Date INDEX BTREE`.
- `airbnb`: convierte `ab_nyc_2019.sql` a CSV compatible y crea `airbnb_locations` con `id INDEX HASH`, `coords POINT2D INDEX RTREE` y `price INDEX BTREE`.
