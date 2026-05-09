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
