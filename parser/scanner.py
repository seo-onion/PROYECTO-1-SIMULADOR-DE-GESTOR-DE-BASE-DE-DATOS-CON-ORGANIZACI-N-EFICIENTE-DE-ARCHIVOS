try:
    from .token import Token, TokenType
except ImportError:
    from token import Token, TokenType

class Scanner:
    def __init__(self, source: str):
        self.input = source
        self.first = 0
        self.current = 0
        self.line = 1
        self.column = 1
        self.current_col = 1
        
        self.keywords = {
            "CREATE": TokenType.CREATE, "TABLE": TokenType.TABLE,
            "INDEX": TokenType.INDEX, "FROM": TokenType.FROM,
            "FILE": TokenType.FILE, "SELECT": TokenType.SELECT,
            "WHERE": TokenType.WHERE, "INSERT": TokenType.INSERT,
            "INTO": TokenType.INTO, "VALUES": TokenType.VALUES,
            "DELETE": TokenType.DELETE, "BETWEEN": TokenType.BETWEEN,
            "AND": TokenType.AND, "IN": TokenType.IN,
            "POINT": TokenType.POINT, "RADIUS": TokenType.RADIUS,
            "K": TokenType.K, "NULL": TokenType.NULL
        }

    def _is_at_end(self) -> bool:
        return self.current >= len(self.input)

    def _peek(self) -> str:
        if self._is_at_end(): return '\0'
        return self.input[self.current]

    def _peek_next(self) -> str:
        if self.current + 1 >= len(self.input): return '\0'
        return self.input[self.current + 1]

    def _advance(self) -> str:
        char = self.input[self.current]
        self.current += 1
        self.current_col += 1
        return char

    def _skip_whitespace(self):
        while True:
            c = self._peek()
            if c in [' ', '\r', '\t']:
                self._advance()
            elif c == '\n':
                self.line += 1
                self.current_col = 1
                self._advance()
            else:
                break

    def next_token(self) -> Token:
        self._skip_whitespace()

        if self._is_at_end():
            return Token(TokenType.EOF, "", self.line, self.column)

        self.first = self.current
        self.column = self.current_col
        c = self._advance()

        # --- Identificadores y Palabras Reservadas-
        if c.isalpha() or c == '_':
            while self._peek().isalnum() or self._peek() == '_':
                self._advance()
            
            text = self.input[self.first:self.current]
            # SQL suele ser case-insensitive para las keywords
            token_type = self.keywords.get(text.upper(), TokenType.ID)
            return Token(token_type, text, self.line, self.column)

        # Números (Soporte para negativos y decimales)
        elif c.isdigit() or (c == '-' and self._peek().isdigit()):
            while self._peek().isdigit():
                self._advance()
            
            # Manejo de decimales para el R-Tree
            if self._peek() == '.' and self._peek_next().isdigit():
                self._advance() # Consumir el '.'
                while self._peek().isdigit():
                    self._advance()
                    
            text = self.input[self.first:self.current]
            return Token(TokenType.NUM, text, self.line, self.column)

        # Strings
        elif c == "'" or c == '"':
            # SQL estándar usa comillas simples para valores, pero soportamos ambas
            quote_type = c
            content = []
            while not self._is_at_end():
                if self._peek() == quote_type:
                    if self._peek_next() == quote_type:
                        # Escaped quote (e.g., '')
                        self._advance() # Consumir la primera comilla
                        content.append(self._advance()) # Consumir y guardar la segunda
                        continue
                    else:
                        # Fin del string
                        break
                
                char = self._advance()
                if char == '\n':
                    self.line += 1
                    self.current_col = 1
                content.append(char)
            
            if self._is_at_end():
                return Token(TokenType.ERR, "Unterminated string", self.line, self.column)
            
            self._advance() # Consumir la comilla de cierre
            return Token(TokenType.STRING, "".join(content), self.line, self.column)

        # Operadores Relacionales (Símbolos compuestos) 
        elif c == '<':
            if self._peek() == '=':
                self._advance()
                return Token(TokenType.LE, "<=", self.line, self.column)
            return Token(TokenType.LT, "<", self.line, self.column)
            
        elif c == '>':
            if self._peek() == '=':
                self._advance()
                return Token(TokenType.GE, ">=", self.line, self.column)
            return Token(TokenType.GT, ">", self.line, self.column)
            
        elif c == '=':
            return Token(TokenType.EQ, "=", self.line, self.column)

        # --- Símbolos simples ---
        elif c == '(': return Token(TokenType.LPAREN, c, self.line, self.column)
        elif c == ')': return Token(TokenType.RPAREN, c, self.line, self.column)
        elif c == ',': return Token(TokenType.COMA, c, self.line, self.column)
        elif c == ';': return Token(TokenType.SEMICOLON, c, self.line, self.column)
        elif c == '*': return Token(TokenType.ASTERISK, c, self.line, self.column)

        # Carácter inválido
        else:
            return Token(TokenType.ERR, c, self.line, self.column)


# --- Función de prueba (Equivalente a tu ejecutar_scanner) ---
def ejecutar_scanner(source_code: str):
    scanner = Scanner(source_code)
    print(f"{'TYPE':<15} | {'TEXT':<15} | {'LINE':<5} | {'COL':<5}")
    print("-" * 45)
    
    while True:
        tok = scanner.next_token()
        if tok.type == TokenType.EOF:
            print(f"{tok.type.name:<15} | {'EOF':<15} | {tok.line:<5} | {tok.column:<5}")
            break
        print(f"{tok.type.name:<15} | {tok.text:<15} | {tok.line:<5} | {tok.column:<5}")
        
        if tok.type == TokenType.ERR:
            print(f">>> ERROR LÉXICO DETENIDO <<<")
            break

if __name__ == "__main__":
    query = "SELECT * FROM users WHERE id = 10 AND location BETWEEN 1.5 AND 10.5;"
    ejecutar_scanner(query)

