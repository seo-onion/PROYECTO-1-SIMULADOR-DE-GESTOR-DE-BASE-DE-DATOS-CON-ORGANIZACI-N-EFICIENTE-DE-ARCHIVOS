from token import TokenType, Token

class ParseError(Exception):
    pass

class SQLParser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.current = 0

    # --- MÉTODOS DE NAVEGACIÓN ---

    def peek(self) -> Token:
        """Devuelve el token actual sin avanzarlo."""
        return self.tokens[self.current]

    def is_at_end(self) -> bool:
        """Verifica si llegamos al final del archivo."""
        return self.peek().type == TokenType.EOF

    def check(self, type: TokenType) -> bool:
        """Revisa si el token actual es del tipo esperado."""
        if self.is_at_end(): return False
        return self.peek().type == type

    def advance(self) -> Token:
        """Avanza al siguiente token y devuelve el que acabamos de pasar."""
        if not self.is_at_end():
            self.current += 1
        return self.tokens[self.current - 1]

    def match(self, *types: TokenType) -> bool:
        """Si el token actual coincide con alguno de los tipos, avanza y retorna True."""
        for t in types:
            if self.check(t):
                self.advance()
                return True
        return False

    def consume(self, type: TokenType, message: str) -> Token:
        """Exige que el token actual sea del tipo esperado. Si no, lanza un error."""
        if self.check(type):
            return self.advance()
        
        token = self.peek()
        raise ParseError(f"Error Sintáctico [Línea {token.line}, Col {token.column}]: {message}. Se encontró '{token.text}'")
    

# Empezamos a Parsear =====================================================================

    def parse(self):
        """Inicia el análisis sintáctico."""
        statements = []
        while not self.is_at_end():
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return statements

    def parse_statement(self):
        """Determina qué tipo de sentencia estamos leyendo."""
        if self.match(TokenType.CREATE):
            return self.parse_create_table()
        elif self.match(TokenType.SELECT):
            return self.parse_select()
        elif self.match(TokenType.INSERT):
            return self.parse_insert()
        elif self.match(TokenType.DELETE):
            return self.parse_delete()
        else:
            # Si no es ninguna palabra clave conocida, lanzamos error
            token = self.peek()
            raise ParseError(f"Error Sintáctico: Sentencia SQL no válida que inicia con '{token.text}'")
        

    # Match Token Type CREATE =================================================================================

    def parse_create_table(self):
        """
        Gramática: 
        CREATE TABLE <id> ( <column_list> ) [ FROM FILE <string> ] ;
        """
        # Nota: asumiendo que el método que llamó a esto ya hizo match(TokenType.CREATE)
        
        self.consume(TokenType.TABLE, "Se esperaba 'TABLE' después de 'CREATE'")
        table_name = self.consume(TokenType.ID, "Se esperaba el nombre de la tabla").text
        
        self.consume(TokenType.LPAREN, "Se esperaba '(' antes de definir las columnas")
        
        # Procesamos la lista de columnas (Mínimo debe haber una)
        columns = []
        columns.append(self.parse_column_def())
        
        # Si hay comas, seguimos leyendo más columnas
        while self.match(TokenType.COMA):
            columns.append(self.parse_column_def())
            
        self.consume(TokenType.RPAREN, "Se esperaba ')' al finalizar las columnas")
        
        # Revisamos si tiene el bloque opcional FROM FILE para cargar el CSV
        file_path = None
        if self.match(TokenType.FROM):
            self.consume(TokenType.FILE, "Se esperaba 'FILE' después de 'FROM'")
            file_path = self.consume(TokenType.STRING, "Se esperaba la ruta del archivo entre comillas").text
            
        self.consume(TokenType.SEMICOLON, "Se esperaba ';' al final de la sentencia CREATE TABLE")
        
        # Construimos nuestro "AST Ligero" como un diccionario
        ast_node = {
            "type": "CREATE_TABLE",
            "table": table_name,
            "columns": columns
        }
        
        if file_path:
            ast_node["from_file"] = file_path
            
        return ast_node

    def parse_column_def(self):
        """
        Gramática:
        <id> <type_def> [ INDEX <index_tech> ]
        """
        col_name = self.consume(TokenType.ID, "Se esperaba el nombre de la columna").text
        
        data_type_parts = []
        paren_depth = 0  # Llevamos la cuenta de los paréntesis abiertos
        
        while True:
            if self.is_at_end():
                raise ParseError("Se alcanzó el fin de archivo leyendo una columna")
                
            # Solo podemos detenernos si NO estamos dentro de unos paréntesis (ej. dentro de VARCHAR(50))
            if paren_depth == 0:
                if self.check(TokenType.COMA) or self.check(TokenType.RPAREN) or self.check(TokenType.INDEX):
                    break  # Salimos del bucle
                    
            token = self.advance()
            data_type_parts.append(token.text)
            
            # Actualizamos la profundidad si encontramos paréntesis
            if token.type == TokenType.LPAREN:
                paren_depth += 1
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
                
        if not data_type_parts:
            raise ParseError(f"Falta definir el tipo de dato para la columna '{col_name}'")
            
        data_type = " ".join(data_type_parts)
        
        col_node = {
            "name": col_name,
            "type": data_type
        }
        
        if self.match(TokenType.INDEX):
            index_tech = self.consume(TokenType.ID, "Se esperaba el nombre de la técnica de indexación").text
            col_node["index"] = index_tech
            
        return col_node
    
    # =================================== SELECT ==========================================

    def parse_select(self):
        """
        Gramática:
        SELECT * FROM <tabla> [ WHERE <condicion> ] ;
        """
        # (Asumimos que 'SELECT' ya fue consumido por parse_statement)
        self.consume(TokenType.ASTERISK, "El subconjunto SQL del proyecto solo soporta SELECT *")
        self.consume(TokenType.FROM, "Se esperaba 'FROM' después de '*'")
        
        table_name = self.consume(TokenType.ID, "Se esperaba el nombre de la tabla").text
        
        condition = None
        # Si hay un WHERE, derivamos el análisis al método parse_condition
        if self.match(TokenType.WHERE):
            condition = self.parse_condition()
            
        self.consume(TokenType.SEMICOLON, "Se esperaba ';' al final de la sentencia SELECT")
        
        # Construimos el AST
        ast_node = {
            "type": "SELECT",
            "table": table_name
        }
        if condition:
            ast_node["condition"] = condition
            
        return ast_node

    def parse_condition(self):
        """
        Deriva a la condición correcta: Simple, Rango (BETWEEN) o Espacial (IN POINT...)
        """
        col_name = self.consume(TokenType.ID, "Se esperaba el nombre de la columna en la condición").text
        
        # 1. Búsqueda por Rango (BETWEEN)
        if self.match(TokenType.BETWEEN):
            val1 = self.parse_value()
            self.consume(TokenType.AND, "Se esperaba 'AND' dentro de la cláusula BETWEEN")
            val2 = self.parse_value()
            return {"type": "range", "column": col_name, "min": val1, "max": val2}
            
        # 2. Búsqueda Espacial R-Tree (IN)
        elif self.match(TokenType.IN):
            self.consume(TokenType.LPAREN, "Se esperaba '(' después de 'IN'")
            self.consume(TokenType.POINT, "Se esperaba 'POINT'")
            self.consume(TokenType.LPAREN, "Se esperaba '(' para las coordenadas del POINT")
            
            x = self.parse_value()
            self.consume(TokenType.COMA, "Se esperaba ',' entre las coordenadas X e Y")
            y = self.parse_value()
            
            self.consume(TokenType.RPAREN, "Se esperaba ')' después de las coordenadas")
            self.consume(TokenType.COMA, "Se esperaba ',' después del POINT")
            
            # Verificamos si es búsqueda por Radio o por K-Vecinos
            if self.match(TokenType.RADIUS):
                radius = self.parse_value()
                self.consume(TokenType.RPAREN, "Se esperaba ')' al final de la condición IN")
                return {"type": "spatial_radius", "column": col_name, "x": x, "y": y, "radius": radius}
                
            elif self.match(TokenType.K):
                k = self.parse_value()
                self.consume(TokenType.RPAREN, "Se esperaba ')' al final de la condición IN")
                return {"type": "spatial_knn", "column": col_name, "x": x, "y": y, "k": k}
                
            else:
                raise ParseError("Se esperaba 'RADIUS' o 'K' en la consulta espacial")
                
        # 3. Búsqueda Puntual o de Operador Simple (=, <, >, <=, >=)
        elif self.match(TokenType.EQ, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE):
            # Recuperamos el token del operador que acabamos de hacer 'match'
            operator = self.tokens[self.current - 1].text
            val = self.parse_value()
            return {"type": "simple", "column": col_name, "op": operator, "val": val}
            
        else:
            token = self.peek()
            raise ParseError(f"Operador no reconocido en el WHERE: '{token.text}'")

    def parse_value(self):
        """
        Convierte el token en un tipo de dato nativo de Python (int, float o string).
        Vital para que el R-Tree pueda operar matemáticamente con los números.
        """
        if self.match(TokenType.NUM):
            val_str = self.tokens[self.current - 1].text
            # Si tiene punto decimal, es float; si no, es int
            return float(val_str) if '.' in val_str else int(val_str)
            
        elif self.match(TokenType.STRING):
            return self.tokens[self.current - 1].text
            
        else:
            token = self.peek()
            raise ParseError(f"Se esperaba un valor (número o texto), pero se encontró '{token.text}'")
        
    # ================================== INSERT ====================================

    def parse_insert(self):
        """
        Gramática:
        INSERT INTO <tabla> VALUES (v1, v2, ...);
        """
        # (Asumimos que 'INSERT' ya fue consumido)
        self.consume(TokenType.INTO, "Se esperaba 'INTO' después de 'INSERT'")
        table_name = self.consume(TokenType.ID, "Se esperaba el nombre de la tabla").text
        
        self.consume(TokenType.VALUES, "Se esperaba 'VALUES'")
        self.consume(TokenType.LPAREN, "Se esperaba '(' antes de los valores")
        
        values = []
        # Parseamos el primer valor (obligatorio)
        values.append(self.parse_value())
        
        # Si hay comas, seguimos leyendo más valores
        while self.match(TokenType.COMA):
            values.append(self.parse_value())
            
        self.consume(TokenType.RPAREN, "Se esperaba ')' al final de los valores")
        self.consume(TokenType.SEMICOLON, "Se esperaba ';' al final de la sentencia INSERT")
        
        return {
            "type": "INSERT",
            "table": table_name,
            "values": values
        }


    # =================================== DELETE ====================================

    def parse_delete(self):
        """
        Gramática:
        DELETE FROM <tabla> WHERE <col> = <valor>;
        """
        # (Asumimos que 'DELETE' ya fue consumido)
        self.consume(TokenType.FROM, "Se esperaba 'FROM' después de 'DELETE'")
        table_name = self.consume(TokenType.ID, "Se esperaba el nombre de la tabla").text
        
        self.consume(TokenType.WHERE, "Se esperaba 'WHERE' en la sentencia DELETE")
        col_name = self.consume(TokenType.ID, "Se esperaba el nombre de la columna").text
        
        self.consume(TokenType.EQ, "Se esperaba '=' en la condición del DELETE")
        val = self.parse_value()
        
        self.consume(TokenType.SEMICOLON, "Se esperaba ';' al final de la sentencia DELETE")
        
        return {
            "type": "DELETE",
            "table": table_name,
            "condition": {
                "column": col_name,
                "op": "=",
                "val": val
            }
        }
    


if __name__ == "__main__":
    import json
    from scanner import Scanner
    from token import TokenType
    
    # Excepción básica por si no la creaste arriba junto a la clase SQLParser
    # class ParseError(Exception): pass

    # Consultas de ejemplo basadas estrictamente en la especificación del proyecto
    queries = [
        # 1. CREATE TABLE (con índice y carga de archivo)
        "CREATE TABLE usuarios (id SERIAL PRIMARY KEY, nombre VARCHAR(50), edad INT INDEX BPlus) FROM FILE 'usuarios.csv';",
        
        # 2. SELECT: Búsqueda puntual y operadores simples
        "SELECT * FROM usuarios WHERE id = 10;",
        "SELECT * FROM usuarios WHERE edad < 25;",
        
        # 3. SELECT: Búsqueda por rango
        "SELECT * FROM usuarios WHERE edad BETWEEN 18 AND 30;",
        
        # 4. SELECT: Búsquedas espaciales en R-Tree
        "SELECT * FROM locales WHERE ubicacion IN (POINT (12.5, -77.2), RADIUS 5.5);",
        "SELECT * FROM locales WHERE ubicacion IN (POINT (12.5, -77.2), K 3);",
        
        # 5. INSERT y DELETE
        "INSERT INTO usuarios VALUES (1, 'Andres', 22);",
        "DELETE FROM usuarios WHERE id = 5;",
        
        # 6. Prueba de error sintáctico (Para ver cómo lo maneja)
        "SELECT * FROM estudiantes WHERE edad >> 20;"
    ]
    
    print("=== INICIANDO PRUEBA COMPLETA DEL PARSER ===")
    
    for query in queries:
        print(f"\n{'-'*50}")
        print(f"📝 Procesando: {query}")
        
        # 1. Scanner: Tokenización
        scanner = Scanner(query)
        tokens = []
        while True:
            tok = scanner.next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF or tok.type == TokenType.ERR:
                break
                
        # 2. Parser: Análisis Sintáctico y Generación del AST
        try:
            parser = SQLParser(tokens)
            ast_resultado = parser.parse() 
            
            print("✅ AST Generado:")
            # Se imprime la lista de sentencias parseadas
            print(json.dumps(ast_resultado, indent=4, ensure_ascii=False))
            
        except Exception as e:
            # Captura tanto tus ParseError como cualquier otro fallo
            print(f"❌ {e}")