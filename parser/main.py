import sys
import os

try:
    from .scanner import Scanner
    from .token import TokenType
except ImportError:
    # Compatibilidad con la ejecución directa previa.
    from scanner import Scanner
    from token import TokenType

def process_file(input_path, output_path):
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        scanner = Scanner(source_code)
        
        results = ["Scanner", ""] # Encabezado solicitado
        
        while True:
            tok = scanner.next_token()
            if tok.type == TokenType.EOF:
                break
            
            # Formato solicitado: TOKEN(TYPE, "TEXT")
            # Escapamos comillas dobles en el texto para no romper el formato
            clean_text = tok.text.replace('"', '\\"')
            results.append(f'TOKEN({tok.type.name}, "{clean_text}")')
            
            if tok.type == TokenType.ERR:
                results.append(f"\n>>> ERROR LÉXICO: '{tok.text}' <<<")
                break
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(results))
        
        print(f"Éxito: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        
    except Exception as e:
        print(f"Error procesando {input_path}: {e}")

def main():
    input_dir = "input"

    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        print(f"Creado directorio: {input_dir}.")
        return

    # Procesamos solo archivos .txt que NO sean archivos de tokens generados por nosotros
    files = [f for f in os.listdir(input_dir) if f.endswith('.txt') and not f.endswith('_tokens.txt')]
    
    if not files:
        print(f"No hay nuevos archivos .txt para procesar en '{input_dir}'")
        return

    for filename in files:
        input_path = os.path.join(input_dir, filename)
        # El resultado se guarda en la misma carpeta input con sufijo _tokens.txt
        output_filename = f"{os.path.splitext(filename)[0]}_tokens.txt"
        output_path = os.path.join(input_dir, output_filename)
        process_file(input_path, output_path)

if __name__ == "__main__":
    main()

# hola muchachitos, estoy probando si puedo pushear mi cosa :D
