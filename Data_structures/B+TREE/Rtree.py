import os
import struct
import math
from typing import List, Sequence, Tuple, Optional

create = 'w+b'
edit   = 'rb+'

# Máximo de entradas por nodo del R-Tree
M = 4   # máximo de hijos/entradas por nodo
m = 2   # mínimo (aprox. M/2)


# ──────────────────────────────────────────────────────────────────────────────
# RTreeNode
# ──────────────────────────────────────────────────────────────────────────────
# Estructura de un nodo:
#   fullness  : int  (cuántas entradas tiene actualmente)
#   is_leaf   : bool
#   Para cada entrada i (hasta M):
#       bbox[i] : 2*dim floats  (min coords + max coords)
#       ptr[i]  : int           (si hoja: row_off del dato; si interno: dirección hijo)
#   address   : dirección en disco (no se serializa, se asigna al leer)

class RTreeNode:
    def __init__(self, dim: int, fullness: int, bboxes: list, pointers: list, is_leaf: bool):
        self.dim      = dim
        self.fullness = fullness
        self.bboxes   = bboxes    # lista de tuplas de 2*dim floats
        self.pointers = pointers  # lista de ints
        self.is_leaf  = is_leaf
        self.address  = -1

    def mbr(self) -> Tuple[float, ...]:
        """Calcula el MBR (Minimum Bounding Rectangle) de todas las entradas."""
        if not self.bboxes:
            return tuple([0.0] * (2 * self.dim))
        dim = self.dim
        mins = list(self.bboxes[0][:dim])
        maxs = list(self.bboxes[0][dim:])
        for bb in self.bboxes[1:]:
            for i in range(dim):
                if bb[i]     < mins[i]: mins[i] = bb[i]
                if bb[dim+i] > maxs[i]: maxs[i] = bb[dim+i]
        return tuple(mins + maxs)

    def print(self):
        print("fullness:", self.fullness)
        print("is_leaf:", self.is_leaf)
        print("address:", self.address)
        for i in range(self.fullness):
            print(f"  [{i}] bbox={self.bboxes[i]}  ptr={self.pointers[i]}")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers geometricos
# ──────────────────────────────────────────────────────────────────────────────

def _bbox_from_point(point: Sequence[float]) -> Tuple[float, ...]:
    p = [float(x) for x in point]
    return tuple(p + p)

def _bbox_area(bbox: Tuple[float, ...], dim: int) -> float:
    area = 1.0
    for i in range(dim):
        area *= max(0.0, bbox[dim + i] - bbox[i])
    return area

def _bbox_union(a: Tuple[float, ...], b: Tuple[float, ...], dim: int) -> Tuple[float, ...]:
    mins = [min(a[i], b[i]) for i in range(dim)]
    maxs = [max(a[dim+i], b[dim+i]) for i in range(dim)]
    return tuple(mins + maxs)

def _bbox_intersects(a: Tuple[float, ...], b: Tuple[float, ...], dim: int) -> bool:
    for i in range(dim):
        if a[i] > b[dim+i] or b[i] > a[dim+i]:
            return False
    return True

def _euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i]))**2 for i in range(len(a))))


# ──────────────────────────────────────────────────────────────────────────────
# RTree
# ──────────────────────────────────────────────────────────────────────────────

class RTree:
    """
    Indice espacial R-Tree persistido en archivo binario puro (sin SQLite).

    Mismo estilo que el Btree del proyecto:
        __init__(filename, column, key_index, dimension=None, rebuild=False)
        insert(point, row_off)
        search(point)                -> List[int]
        range_search(point, radius)  -> List[int]
        knn_search(point, k)         -> List[int]
        delete(row_off)              -> List[int]

    Formato del archivo .bin
    ────────────────────────
    HEADER  (16 bytes):
        node_count : i   cantidad de nodos creados
        dim        : i   dimensiones del vector
        root_ptr   : i   direccion del nodo raiz
        free_list  : i   primer nodo liberado (-1 si no hay)

    NODO  (node_size bytes):
        fullness   : i
        is_leaf    : b  (1 byte)
        pad        : 3b (alineacion)
        Por cada slot i in range(M):
            bbox[i]  : 2*dim floats ('f' cada uno)
            ptr[i]   : i
    """

    HEADER_SIZE = struct.calcsize('= i i i i')   # 16 bytes

    def __init__(
        self,
        filename: str,
        column: str,
        key_index: int,
        dimension: Optional[int] = None,
        rebuild: bool = False,
    ):
        self.db_name   = filename
        self.column    = column
        self.key_index = key_index
        self.dim       = int(dimension) if dimension else self._parse_dimension(column)

        # Mismo patron de nombre que Btree: filename + "rtree" + "_index" + key_index
        self.rtree_file_name = filename + "rtree" + "_index" + str(key_index) + ".bin"

        # Tamano de nodo: 4 (fullness) + 1 (is_leaf) + 3 (pad) + M * (2*dim*4 + 4)
        self._float_fmt  = '= ' + 'f' * (2 * self.dim)
        self._float_size = struct.calcsize(self._float_fmt)
        self._slot_size  = self._float_size + struct.calcsize('= i')
        self.node_size   = 4 + 1 + 3 + M * self._slot_size

        if rebuild and os.path.exists(self.rtree_file_name):
            os.remove(self.rtree_file_name)

        if os.path.exists(self.rtree_file_name):
            self.__check_header()
        else:
            self.__initialize_header()
            root = RTreeNode(self.dim, 0, [], [], True)
            self.__write_node(root, self.HEADER_SIZE)

    # ── Parseo de dimension ───────────────────────────────────────────────────

    @staticmethod
    def _parse_dimension(column: str) -> int:
        n = 0
        for ch in column:
            if ch.isdigit():
                n = n * 10 + int(ch)
            else:
                break
        return n if n > 0 else 2

    # ── Header ────────────────────────────────────────────────────────────────

    def __initialize_header(self):
        with open(self.rtree_file_name, create) as f:
            f.seek(0)
            f.write(struct.pack('= i', 1))                # node_count
            f.write(struct.pack('= i', self.dim))          # dim
            f.write(struct.pack('= i', self.HEADER_SIZE))  # root_ptr
            f.write(struct.pack('= i', -1))                # free_list

    def __check_header(self):
        _, dim, _, _ = self.__read_header()
        if dim != self.dim:
            raise Exception(
                f"El archivo rtree tiene dimension {dim} pero se pidio {self.dim}"
            )

    def __read_header(self):
        with open(self.rtree_file_name, edit) as f:
            f.seek(0)
            return struct.unpack('= i i i i', f.read(self.HEADER_SIZE))
        # retorna: node_count, dim, root_ptr, free_list

    def __get_root(self) -> int:
        with open(self.rtree_file_name, edit) as f:
            f.seek(8)
            return struct.unpack('= i', f.read(4))[0]

    def __update_root(self, ptr: int):
        with open(self.rtree_file_name, edit) as f:
            f.seek(8)
            f.write(struct.pack('= i', ptr))

    def __get_free_list(self) -> int:
        with open(self.rtree_file_name, edit) as f:
            f.seek(12)
            return struct.unpack('= i', f.read(4))[0]

    def __update_free_list(self, ptr: int):
        with open(self.rtree_file_name, edit) as f:
            f.seek(12)
            f.write(struct.pack('= i', ptr))

    def __update_node_count(self, count: int):
        with open(self.rtree_file_name, edit) as f:
            f.seek(0)
            f.write(struct.pack('= i', count))

    def __index_to_address(self, index: int) -> int:
        return self.HEADER_SIZE + index * self.node_size

    def __next_free_address(self) -> int:
        node_count, _, _, free_list = self.__read_header()
        if free_list == -1:
            self.__update_node_count(node_count + 1)
            return self.__index_to_address(node_count)
        # Reutilizar nodo liberado (igual que Btree)
        node = self.__read_node(free_list)
        next_free = node.pointers[0] if node.pointers else -1
        self.__update_free_list(next_free)
        return free_list

    # ── Serializacion de nodos ────────────────────────────────────────────────

    def __write_node(self, node: RTreeNode, address: int):
        with open(self.rtree_file_name, edit) as f:
            f.seek(address)
            f.write(struct.pack('= i', node.fullness))
            f.write(struct.pack('= b', int(node.is_leaf)))
            f.write(b'\x00' * 3)   # padding de alineacion

            for i in range(M):
                if i < node.fullness:
                    bbox = node.bboxes[i]
                    ptr  = node.pointers[i]
                else:
                    bbox = (0.0,) * (2 * self.dim)
                    ptr  = -1
                f.write(struct.pack(self._float_fmt, *bbox))
                f.write(struct.pack('= i', ptr))

    def __read_node(self, address: int) -> RTreeNode:
        with open(self.rtree_file_name, edit) as f:
            f.seek(address)
            fullness = struct.unpack('= i', f.read(4))[0]
            is_leaf  = bool(struct.unpack('= b', f.read(1))[0])
            f.read(3)   # padding

            bboxes   = []
            pointers = []
            for i in range(M):
                raw  = f.read(self._float_size)
                bbox = struct.unpack(self._float_fmt, raw)
                ptr  = struct.unpack('= i', f.read(4))[0]
                if i < fullness:
                    bboxes.append(bbox)
                    pointers.append(ptr)

        node = RTreeNode(self.dim, fullness, bboxes, pointers, is_leaf)
        node.address = address
        return node

    # ── Insert ────────────────────────────────────────────────────────────────

    def insert(self, point: Sequence[float], row_off: int) -> None:
        """
        Inserta un punto en el indice.
        point   : coordenadas del vector
        row_off : offset de la fila en el heap (equivalente a `ptr` en Btree)
        """
        if len(point) != self.dim:
            raise ValueError(f"Dimension incorrecta: {len(point)}D vs {self.dim}D")

        bbox     = _bbox_from_point(point)
        root_ptr = self.__get_root()
        result   = self.__recursive_insert_and_split(root_ptr, bbox, int(row_off))

        if result is not None:
            # La raiz se dividio; crear nueva raiz con dos hijos
            left, right = result
            new_root = RTreeNode(
                self.dim, 2,
                [left.mbr(), right.mbr()],
                [left.address, right.address],
                False
            )
            new_root_addr    = self.__next_free_address()
            new_root.address = new_root_addr
            self.__write_node(new_root, new_root_addr)
            self.__update_root(new_root_addr)

    def __recursive_insert_and_split(self, node_addr: int, bbox: Tuple[float, ...], ptr: int):
        """
        Inserta bbox/ptr en el subarbol con raiz en node_addr.
        Retorna None si no hubo split, o (nodo_izq, nodo_der) si hubo split.
        """
        node = self.__read_node(node_addr)

        if node.is_leaf:
            node.bboxes.append(bbox)
            node.pointers.append(ptr)
            node.fullness += 1

            if node.fullness > M:
                return self.__split_node(node)
            else:
                self.__write_node(node, node_addr)
                return None
        else:
            chosen_i = self.__choose_subtree(node, bbox)
            result   = self.__recursive_insert_and_split(node.pointers[chosen_i], bbox, ptr)

            if result is None:
                # Actualizar MBR del hijo elegido
                child = self.__read_node(node.pointers[chosen_i])
                node.bboxes[chosen_i] = child.mbr()
                self.__write_node(node, node_addr)
                return None
            else:
                left, right = result
                # Reemplazar entrada del hijo que se dividio
                node.bboxes[chosen_i]   = left.mbr()
                node.pointers[chosen_i] = left.address
                # Agregar nueva entrada del hermano derecho
                node.bboxes.append(right.mbr())
                node.pointers.append(right.address)
                node.fullness += 1

                if node.fullness > M:
                    return self.__split_node(node)
                else:
                    self.__write_node(node, node_addr)
                    return None

    def __choose_subtree(self, node: RTreeNode, bbox: Tuple[float, ...]) -> int:
        """Indice del hijo cuyo MBR requiere el menor incremento de area."""
        best_i    = 0
        best_inc  = float('inf')
        best_area = float('inf')
        for i in range(node.fullness):
            union    = _bbox_union(node.bboxes[i], bbox, self.dim)
            area_new = _bbox_area(union, self.dim)
            area_old = _bbox_area(node.bboxes[i], self.dim)
            inc = area_new - area_old
            if inc < best_inc or (inc == best_inc and area_old < best_area):
                best_i    = i
                best_inc  = inc
                best_area = area_old
        return best_i

    def __split_node(self, node: RTreeNode) -> Tuple[RTreeNode, RTreeNode]:
        """
        Split lineal: elige las dos semillas mas alejadas y distribuye el resto.
        Retorna (nodo_izq, nodo_der) ya escritos en disco.
        """
        dim     = self.dim
        entries = list(zip(node.bboxes, node.pointers))

        s1, s2 = self.__linear_pick_seeds(entries)

        left  = RTreeNode(dim, 1, [entries[s1][0]], [entries[s1][1]], node.is_leaf)
        right = RTreeNode(dim, 1, [entries[s2][0]], [entries[s2][1]], node.is_leaf)

        remaining = [e for i, e in enumerate(entries) if i not in (s1, s2)]

        for idx, (bb, p) in enumerate(remaining):
            mbr_l = left.mbr()
            mbr_r = right.mbr()
            inc_l = _bbox_area(_bbox_union(mbr_l, bb, dim), dim) - _bbox_area(mbr_l, dim)
            inc_r = _bbox_area(_bbox_union(mbr_r, bb, dim), dim) - _bbox_area(mbr_r, dim)

            # Garantizar minimo m entradas en cada nodo
            slots_left = len(remaining) - idx
            if left.fullness + slots_left <= m:
                target = left
            elif right.fullness + slots_left <= m:
                target = right
            elif inc_l <= inc_r:
                target = left
            else:
                target = right

            target.bboxes.append(bb)
            target.pointers.append(p)
            target.fullness += 1

        # El nodo izquierdo reutiliza la direccion original
        left.address = node.address
        self.__write_node(left, left.address)

        right_addr    = self.__next_free_address()
        right.address = right_addr
        self.__write_node(right, right_addr)

        return left, right

    def __linear_pick_seeds(self, entries):
        """Par de indices con mayor distancia euclidiana entre centros de sus bboxes."""
        dim = self.dim
        best_dist = -1.0
        s1, s2 = 0, 1
        for i in range(len(entries)):
            ci = [(entries[i][0][d] + entries[i][0][dim+d]) / 2 for d in range(dim)]
            for j in range(i+1, len(entries)):
                cj = [(entries[j][0][d] + entries[j][0][dim+d]) / 2 for d in range(dim)]
                dist = _euclidean(ci, cj)
                if dist > best_dist:
                    best_dist = dist
                    s1, s2 = i, j
        return s1, s2

    # ── Search exacto ─────────────────────────────────────────────────────────

    def search(self, point: Sequence[float]) -> List[int]:
        """
        Busqueda exacta de punto. Devuelve lista de row_off que coinciden.
        Analogo a Btree.search(val, ptr).
        """
        if len(point) != self.dim:
            raise ValueError(f"Dimension incorrecta: {len(point)}D vs {self.dim}D")
        bbox   = _bbox_from_point(point)
        result: List[int] = []
        self.__search_recursive(self.__get_root(), bbox, result, exact=True)
        return result

    # ── Range search ──────────────────────────────────────────────────────────

    def range_search(self, point: Sequence[float], radius: float) -> List[int]:
        """
        Devuelve todos los row_off cuyo punto esta dentro de `radius` del `point`.
        Analogo a Btree.range_search(low, high).
        """
        if len(point) != self.dim:
            raise ValueError(f"Dimension incorrecta: {len(point)}D vs {self.dim}D")
        p = [float(x) for x in point]
        r = float(radius)
        # Bounding box cuadrado para poda rapida del arbol
        query_bbox = tuple([p[i] - r for i in range(self.dim)] +
                           [p[i] + r for i in range(self.dim)])
        result: List[int] = []
        self.__search_recursive(self.__get_root(), query_bbox, result, exact=False)
        return result

    def __search_recursive(self, node_addr: int, query_bbox: Tuple[float, ...],
                           result: List[int], exact: bool):
        node = self.__read_node(node_addr)
        for i in range(node.fullness):
            if not _bbox_intersects(node.bboxes[i], query_bbox, self.dim):
                continue
            if node.is_leaf:
                if exact:
                    if node.bboxes[i] == query_bbox:
                        result.append(node.pointers[i])
                else:
                    result.append(node.pointers[i])
            else:
                self.__search_recursive(node.pointers[i], query_bbox, result, exact)

    # ── KNN search ────────────────────────────────────────────────────────────

    def knn_search(self, point: Sequence[float], k: int) -> List[int]:
        """
        Devuelve los k vecinos mas cercanos (row_off).
        Usa Best-First search sobre el R-Tree (algoritmo de Hjaltason & Samet).
        """
        if len(point) != self.dim:
            raise ValueError(f"Dimension incorrecta: {len(point)}D vs {self.dim}D")
        import heapq
        p = tuple(float(x) for x in point)
        k = max(1, int(k))

        def min_dist_to_bbox(bbox) -> float:
            d = 0.0
            for i in range(self.dim):
                if p[i] < bbox[i]:
                    d += (bbox[i] - p[i]) ** 2
                elif p[i] > bbox[self.dim + i]:
                    d += (p[i] - bbox[self.dim + i]) ** 2
            return math.sqrt(d)

        # heap: (distancia_minima, es_entrada_hoja, direccion_o_rowoff)
        heap: list = []
        heapq.heappush(heap, (0.0, False, self.__get_root()))

        result: List[int] = []
        while heap and len(result) < k:
            dist, is_leaf_entry, addr_or_row = heapq.heappop(heap)
            if is_leaf_entry:
                result.append(addr_or_row)
                continue
            node = self.__read_node(addr_or_row)
            for i in range(node.fullness):
                d = min_dist_to_bbox(node.bboxes[i])
                if node.is_leaf:
                    heapq.heappush(heap, (d, True, node.pointers[i]))
                else:
                    heapq.heappush(heap, (d, False, node.pointers[i]))

        return result

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self, row_off: int) -> List[int]:
        """
        Elimina del indice la entrada con el row_off dado.
        Devuelve [row_off] si tuvo exito, [-1] si no se encontro.
        Analogo a Btree.delete(val, ptr).
        """
        root_ptr = self.__get_root()
        removed  = self.__recursive_delete(root_ptr, int(row_off))
        if not removed:
            return [-1]
        return [row_off]

    def __recursive_delete(self, node_addr: int, row_off: int) -> bool:
        node = self.__read_node(node_addr)

        if node.is_leaf:
            for i in range(node.fullness):
                if node.pointers[i] == row_off:
                    node.bboxes.pop(i)
                    node.pointers.pop(i)
                    node.fullness -= 1
                    self.__write_node(node, node_addr)
                    return True
            return False
        else:
            for i in range(node.fullness):
                if self.__recursive_delete(node.pointers[i], row_off):
                    child = self.__read_node(node.pointers[i])
                    if child.fullness == 0:
                        # Hijo vacio: liberarlo (igual que Btree.__delete_node)
                        free_list = self.__get_free_list()
                        self.__update_free_list(child.address)
                        empty = RTreeNode(self.dim, -1, [], [free_list], False)
                        self.__write_node(empty, child.address)
                        node.bboxes.pop(i)
                        node.pointers.pop(i)
                        node.fullness -= 1
                    else:
                        node.bboxes[i] = child.mbr()
                    self.__write_node(node, node_addr)
                    return True
            return False